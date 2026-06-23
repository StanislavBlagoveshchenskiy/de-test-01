"""
Настройка Metabase через REST API (только стандартная библиотека).

Запускается после старта Metabase и безопасен к повторам: ждёт готовности,
создаёт админа или логинится, подключает Postgres (casino), дожидается витрины
monthly_summary (её делает dbt в DAG) и собирает дашборд «Casino overview».
Повторный запуск дубликатов не создаёт; если витрины ещё нет — структуру всё
равно строим, наполнится после прогона DAG.

Параметры — из переменных окружения (см. docker-compose).
"""
import json
import os
import time
import urllib.error
import urllib.request

MB = os.environ.get("MB_URL", "http://metabase:3000")
ADMIN_EMAIL = os.environ.get("MB_ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.environ.get("MB_ADMIN_PASSWORD", "Metabase123!")
SITE_NAME = os.environ.get("MB_SITE_NAME", "DE Test")
DASH_NAME = os.environ.get("MB_DASHBOARD_NAME", "Casino overview")

# Сколько ждём появления витрины monthly_summary (её наполняет DAG/dbt).
VIEW_RETRIES = int(os.environ.get("MB_WAIT_VIEW_RETRIES", "60"))
VIEW_DELAY = int(os.environ.get("MB_WAIT_VIEW_DELAY", "5"))

PG = {
    "host": os.environ.get("MB_PG_HOST", "postgres"),
    "port": int(os.environ.get("MB_PG_PORT", "5432")),
    "dbname": os.environ.get("MB_PG_DB", "casino"),
    "user": os.environ.get("MB_PG_USER", "postgres"),
    "password": os.environ.get("MB_PG_PASSWORD", "postgres"),
}


def req(method, path, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Metabase-Session"] = token
    body = json.dumps(data).encode() if data is not None else None
    r = urllib.request.Request(MB + path, data=body, headers=headers, method=method)
    with urllib.request.urlopen(r, timeout=30) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else None


def wait_ready(retries=120, delay=5):
    for i in range(retries):
        try:
            req("GET", "/api/health")
            print("[metabase-init] Metabase готов")
            return True
        except Exception as e:  # noqa: BLE001
            print(f"[metabase-init] ждём Metabase ({i + 1}/{retries})… {e}")
            time.sleep(delay)
    return False


def pg_details():
    return {
        "host": PG["host"],
        "port": PG["port"],
        "dbname": PG["dbname"],
        "user": PG["user"],
        "password": PG["password"],
        "ssl": False,
        "schema-filters-type": "all",
    }


def get_session():
    """Возвращает session-token: setup при первом запуске, иначе обычный логин."""
    props = req("GET", "/api/session/properties")
    if props.get("has-user-setup"):
        print("[metabase-init] setup уже выполнен — логинюсь под админом")
        session = req("POST", "/api/session",
                      {"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        return session["id"] if isinstance(session, dict) else session

    # Источник данных НЕ передаём в /api/setup: в ряде версий Metabase он там
    # не регистрируется. Подключаем Postgres отдельно и идемпотентно (ensure_db).
    session = req("POST", "/api/setup", {
        "token": props["setup-token"],
        "user": {
            "first_name": "Admin",
            "last_name": "User",
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
            "site_name": SITE_NAME,
        },
        "prefs": {"site_name": SITE_NAME, "allow_tracking": False},
    })
    print("[metabase-init] админ создан")
    return session["id"] if isinstance(session, dict) else session


def find_db_id(token):
    dbs = req("GET", "/api/database", token=token)
    db_list = dbs["data"] if isinstance(dbs, dict) and "data" in dbs else dbs
    return next((d["id"] for d in (db_list or []) if d.get("name") == "casino"), None)


def ensure_db(token, retries=15, delay=2):
    """Идемпотентно гарантирует подключение Postgres (casino) и возвращает его id."""
    db_id = find_db_id(token)
    if db_id is not None:
        print("[metabase-init] подключение casino уже есть")
        return db_id

    print("[metabase-init] подключаю Postgres (casino)")
    try:
        created = req("POST", "/api/database", token=token,
                      data={"engine": "postgres", "name": "casino", "details": pg_details()})
        if isinstance(created, dict) and created.get("id") is not None:
            return created["id"]
    except Exception as e:  # noqa: BLE001
        print(f"[metabase-init] не удалось создать подключение: {e}")

    # каталог обновляется асинхронно — короткий доопрос
    for _ in range(retries):
        db_id = find_db_id(token)
        if db_id is not None:
            return db_id
        time.sleep(delay)
    return None


def view_ready(token, db_id):
    """True, если native-запрос к витрине отрабатывает (значит вьюха существует)."""
    try:
        res = req("POST", "/api/dataset", token=token, data={
            "database": db_id,
            "type": "native",
            "native": {"query": "SELECT 1 FROM analytics.monthly_summary LIMIT 1"},
        })
        return isinstance(res, dict) and res.get("status") == "completed"
    except Exception:  # noqa: BLE001
        return False


def wait_for_view(token, db_id):
    for i in range(VIEW_RETRIES):
        if view_ready(token, db_id):
            print("[metabase-init] витрина monthly_summary готова")
            return True
        print(f"[metabase-init] жду витрину monthly_summary ({i + 1}/{VIEW_RETRIES})…")
        time.sleep(VIEW_DELAY)
    print("[metabase-init] витрина не появилась вовремя — собираю дашборд как есть "
          "(наполнится после прогона DAG)")
    return False


def dashboard_exists(token, name):
    res = req("GET", "/api/dashboard", token=token)
    items = res["data"] if isinstance(res, dict) and "data" in res else res
    return any(d.get("name") == name for d in (items or []))


def main():
    if not wait_ready():
        raise SystemExit("[metabase-init] Metabase не поднялся вовремя")

    token = get_session()

    db_id = ensure_db(token)
    if db_id is None:
        print("[metabase-init] не нашёл БД casino — дашборд пропускаю")
        return

    # просим Metabase просканировать схему (native-карточки работают и без этого)
    try:
        req("POST", f"/api/database/{db_id}/sync_schema", token=token)
    except Exception:  # noqa: BLE001
        pass

    if dashboard_exists(token, DASH_NAME):
        print(f"[metabase-init] дашборд '{DASH_NAME}' уже существует — пропускаю")
        return

    # ждём витрину, чтобы дашборд был сразу с данными
    wait_for_view(token, db_id)

    try:
        provision_dashboard(token, db_id)
    except Exception as e:  # noqa: BLE001
        print(f"[metabase-init] дашборд не собрался (некритично): {e}")
        print("[metabase-init] соберите дашборд вручную (metabase/README.md)")


def make_card(token, db_id, name, query, display, viz):
    card = req("POST", "/api/card", token=token, data={
        "name": name,
        "dataset_query": {
            "type": "native",
            "native": {"query": query},
            "database": db_id,
        },
        "display": display,
        "visualization_settings": viz,
    })
    return card["id"]


def provision_dashboard(token, db_id):
    c1 = make_card(
        token, db_id, "Динамика по месяцам (USD)",
        "SELECT month, total_deposits_usd, total_withdrawals_usd, total_bets_usd "
        "FROM analytics.monthly_summary ORDER BY month",
        "line",
        {"graph.dimensions": ["month"],
         "graph.metrics": ["total_deposits_usd", "total_withdrawals_usd", "total_bets_usd"]},
    )
    c2 = make_card(
        token, db_id, "Распределение по странам (USD)",
        "SELECT country, SUM(total_deposits_usd) AS deposits, "
        "SUM(total_withdrawals_usd) AS withdrawals, SUM(total_bets_usd) AS bets "
        "FROM analytics.monthly_summary GROUP BY country ORDER BY deposits DESC",
        "bar",
        {"graph.dimensions": ["country"],
         "graph.metrics": ["deposits", "withdrawals", "bets"]},
    )

    dash = req("POST", "/api/dashboard", token=token, data={"name": DASH_NAME})
    dash_id = dash["id"]

    dashcards = [
        {"id": -1, "card_id": c1, "row": 0, "col": 0, "size_x": 12, "size_y": 7},
        {"id": -2, "card_id": c2, "row": 7, "col": 0, "size_x": 12, "size_y": 7},
    ]
    # Новые версии: PUT с dashcards; старые: POST /cards. Пробуем оба.
    try:
        req("PUT", f"/api/dashboard/{dash_id}", token=token, data={"dashcards": dashcards})
    except Exception:  # noqa: BLE001
        for dc in dashcards:
            req("POST", f"/api/dashboard/{dash_id}/cards", token=token,
                data={"cardId": dc["card_id"], "row": dc["row"], "col": dc["col"],
                      "size_x": dc["size_x"], "size_y": dc["size_y"]})
    print(f"[metabase-init] дашборд '{DASH_NAME}' собран (id={dash_id})")


if __name__ == "__main__":
    main()
