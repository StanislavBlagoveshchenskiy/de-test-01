# Data Engineer — тестовое задание

ETL-пайплайн для аналитики игровой платформы: загрузка исходных CSV в PostgreSQL,
трансформация через **dbt**, построение витрины **`monthly_summary`** (суммы депозитов,
выводов и ставок в USD по месяцам и странам), визуализация в **Metabase** и в виде
**Python-графиков**. Оркестрация — **Airflow** (CeleryExecutor). Всё поднимается одной
командой через **Docker Compose**.

---

## 1. Архитектура

```
                 ┌─────────────────────── Airflow (CeleryExecutor) ───────────────────────┐
   CSV  ──load──▶│  load_csv ──▶ dbt run ──▶ dbt test ──▶ build_charts                     │
 (./data)        └───────┬───────────────────┬───────────────────────┬─────────────────────┘
                         ▼                   ▼                        ▼
                   PostgreSQL          PostgreSQL                 ./reports
                   raw.*  таблицы      analytics.*  (views)       PNG + HTML
                         │                   │
                         └──────► monthly_summary (VIEW) ◄──── Metabase (BI)
```

- **PostgreSQL** — данные проекта (БД `casino`, схемы `raw` и `analytics`) и метаданные Airflow (БД `airflow`).
- **Airflow** — Scheduler + Webserver + Worker + Redis (брокер Celery).
- **dbt** — staging-модели + витрина `monthly_summary` + тесты данных.
- **Metabase** — BI-дашборды поверх витрины.
- **Python (matplotlib/plotly)** — те же графики кодом, сохраняются в `./reports`.

Почему именно такой стек — коротко в §11.

---

## 2. Prerequisites

- **Docker Desktop** (с Docker Compose v2) — на Windows и macOS идёт в комплекте.
- Выделить Docker ≥ **4 GB RAM** (Airflow + Celery + Metabase).
- Свободные порты: **8080** (Airflow), **3000** (Metabase), **5432** (Postgres). Меняются в `.env`.

---

## 3. Запуск с нуля (одна команда)

```bash
git clone <repo-url>
cd de-test-01

docker compose up -d --build      # или:  make up
```

Это **всё, что нужно** для проверки. Файл `.env` создавать не обязательно — все
дефолты (порты, логины, пароли) уже зашиты в `docker-compose.yml`. `.env` нужен,
только если хотите переопределить значения (см. `.env.example`).

> **Mac/Linux (опционально):** для корректных прав на смонтированные тома —
> `echo "AIRFLOW_UID=$(id -u)" > .env` перед запуском. На Windows не требуется.

Первый старт качает образы и собирает кастомный образ Airflow+dbt — это занимает
несколько минут. Дождитесь, пока сервисы станут `healthy`:

```bash
docker compose ps        # или: make ps
```

### Куда идти — сервисы, порты, логины

Все сервисы поднимаются на **`localhost`** (порты проброшены на хост):

| Сервис   | Адрес                   | Логин / пароль            | Что это |
|----------|-------------------------|---------------------------|---------|
| **Airflow**  | http://localhost:8080 | `admin` / `admin`        | оркестратор, граф DAG |
| **Metabase** | http://localhost:3000 | `admin@example.com` / `Metabase123!` | BI-дашборд (создаётся автоматически) |
| **Postgres** | `localhost:5432`      | `postgres` / `postgres`  | данные проекта, БД `casino` |

**Подключение к Postgres (DBeaver / psql / любой клиент):**

| Параметр | Значение |
|---|---|
| Host | `localhost` |
| Port | `5432` |
| Database | `casino` |
| User / Password | `postgres` / `postgres` |

Схемы в БД `casino`: **`raw`** (сырые данные из CSV), **`analytics`** (staging-модели
dbt + витрина `monthly_summary`). БД `airflow` в том же сервере — это служебные
метаданные Airflow, в неё ходить не нужно.

### Запуск ETL

DAG `etl_monthly_summary` создаётся **не на паузе** и запускается по расписанию
(`@monthly`). Чтобы прогнать сразу, не дожидаясь расписания:

```bash
make trigger
# или без make:
docker compose exec airflow-scheduler airflow dags trigger etl_monthly_summary
```

После прогона:
- витрина доступна как `analytics.monthly_summary` в БД `casino`;
- графики появятся в `./reports/` (`monthly_dynamics.*`, `by_country.*`);
- дашборд «Casino overview» в Metabase наполнится данными.

---

## 3.1. Что смотреть проверяющему (чек-лист)

1. **Airflow** → http://localhost:8080 (`admin`/`admin`) → DAG **`etl_monthly_summary`**:
   граф из 4 тасков `load_csv → dbt_run → dbt_test → build_charts`, все зелёные.
2. **Metabase** → http://localhost:3000 (`admin@example.com`/`Metabase123!`) →
   дашборд **«Casino overview»**: динамика по месяцам + распределение по странам.
3. **Витрина в БД** — через DBeaver/psql (параметры выше):
   ```sql
   SELECT * FROM analytics.monthly_summary ORDER BY month, country LIMIT 20;
   ```
4. **Python-графики** — файлы в каталоге **`./reports/`**
   (`monthly_dynamics.png/.html`, `by_country.png/.html`).
5. **Тесты данных** — `make test` (см. §6), все dbt-тесты проходят.

---

## 4. Как работает ETL / DAG

DAG `etl_monthly_summary` (файл `dags/etl_monthly_summary.py`), 4 таска по цепочке:

1. **`load_csv`** — грузит CSV из `./data` в схему `raw`. Идемпотентно:
   `INSERT ... ON CONFLICT DO NOTHING` по PK → **повторный запуск не плодит дубликаты**.
   Порядок загрузки учитывает FK (справочники и `players` — раньше транзакций).
2. **`dbt_run`** — строит staging-модели и витрину `monthly_summary`.
3. **`dbt_test`** — прогоняет тесты данных (см. §6).
4. **`build_charts`** — генерирует графики в `./reports`.

Расписание `@monthly`, `catchup=False` — витрина пересобирается раз в месяц,
историю не догоняем.

---

## 5. Модель данных

Слои: `raw` (1:1 из CSV) → `staging` (типизация + конвертация в USD) → `marts`
(`monthly_summary`). ERD и слои — в [`docs/erd.md`](docs/erd.md).

**Витрина `monthly_summary`** (грануляция месяц × страна):

| Поле | Смысл |
|---|---|
| `month` | первый день месяца транзакции |
| `country` | страна игрока (из `players`) |
| `total_deposits_usd` / `total_withdrawals_usd` / `total_bets_usd` | суммы в USD |
| `net_usd` | депозиты − выводы |
| `deposits_cnt` / `withdrawals_cnt` / `bets_cnt` | счётчики операций |

### Допущения

Пара мест в данных трактуется неоднозначно — фиксирую решения здесь:

1. **Направление конвертации валют.** Колонка `rate_to_usd` неоднозначна: для RUB это
   «рублей за 1 USD» (~65–75), для EUR/GBP ~0.8–1.2. Согласованно по всем валютам работает
   только **деление**: `amount_usd = amount / rate_to_usd` (умножение дало бы 1 RUB ≈ 65 USD).
   Вся конвертация в одном макросе [`dbt/macros/to_usd.sql`](dbt/macros/to_usd.sql) —
   если правильнее умножение, менять там.
2. **Курс на дату транзакции.** Берётся курс с датой ≤ даты транзакции (последний известный),
   через LATERAL «as-of» джойн — устойчиво к возможным пропускам курсов.
3. **Грануляция витрины** — месяц × страна. Легко расширяется (провайдер, валюта).
4. **Знаки сумм.** Все `amount` положительные; «выводы» вычитаются в `net_usd` на уровне витрины.

---

## 6. Тесты

dbt-тесты (схема + данные), запускаются таском `dbt_test` или вручную:

```bash
make test
# или:
docker compose exec airflow-worker /opt/dbt-venv/bin/dbt test \
  --project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt
```

Покрытие:
- `not_null` + `unique` на PK всех staging-моделей;
- `relationships` (FK-целостность): `player_id`→`players`, `provider_id`→`providers_map`, `game_id`→`games_map`;
- `accepted_values`: валюты, страны, типы регистрации;
- витрина: `not_null` на ключевых полях, **отсутствие отрицательных сумм** (`non_negative`),
  уникальность зерна `(month, country)`.

---

## 7. Визуализация

**Python** (`viz/build_charts.py`) читает `monthly_summary` и строит в `./reports`:

1. `monthly_dynamics.png/.html` — динамика депозитов / выводов / ставок по месяцам
   (поля `total_*_usd`, group by `month`).
2. `by_country.png/.html` — распределение тех же сумм по странам (group by `country`).

PNG — статичные (matplotlib), HTML — интерактивные (plotly). Пересобрать: `make viz`.

**Metabase** (http://localhost:3000): подключение и дашборд настраиваются
**автоматически** сервисом `metabase-init` после старта — он создаёт админа,
подключает PostgreSQL (БД `casino`) и собирает дашборд «Casino overview» с теми же
двумя графиками поверх `analytics.monthly_summary`.

Провижининг **идемпотентен и устойчив к порядку старта**: скрипт сам дожидается
готовности Metabase, надёжно подключает источник данных и ждёт появления витрины
`monthly_summary` (её создаёт DAG), поэтому дашборд собирается при любом запуске и
сразу с данными. Повторные `docker compose up` дубликатов не создают. Если витрина
ещё не готова к моменту провижининга — структура дашборда всё равно создаётся и
наполнится после прогона DAG. Детали и ручная сборка — в `metabase/README.md`.

---

## 8. Troubleshooting (кросс-платформенность Windows ↔ Mac)

- **CRLF/LF.** Репозиторий нормализует окончания строк через `.gitattributes` (`eol=lf`).
  Если клонировали с CRLF и bash-скрипты «ломаются» — переклонируйте либо `git config core.autocrlf input`.
- **AIRFLOW_UID (Mac/Linux).** Если логи/тома пишутся с ошибкой прав — задайте
  `echo "AIRFLOW_UID=$(id -u)" >> .env` и пересоздайте: `docker compose down && docker compose up -d`.
  На Windows переменная игнорируется (это нормально).
- **Apple Silicon (arm64).** Все образы официальные multi-arch — эмуляция не нужна.
- **Порты заняты.** Поменяйте `*_PORT` в `.env`.
- **Мало RAM.** Поднимите лимит Docker Desktop до ≥ 4 GB.
- **Метаданные не пересоздаются.** init-скрипты Postgres применяются только на ПУСТОМ
  volume. Полный сброс: `make clean` (`docker compose down -v`), затем `up`.

---

## 9. Teardown

```bash
docker compose down       # остановить (данные в volumes сохраняются)
docker compose down -v    # полный сброс, включая БД и метаданные  (make clean)
```

---

## 10. Структура репозитория

```
.
├── docker-compose.yml          # вся инфраструктура
├── .env.example                # дефолты конфигурации
├── Makefile                    # up/down/trigger/test/viz (Mac/Linux)
├── docker/airflow/Dockerfile   # Airflow + dbt (в изолированном venv)
├── data/                       # исходные CSV
├── sql/init/                   # DDL: схема, индексы, FK, БД airflow
├── dags/etl_monthly_summary.py # DAG
├── dbt/                        # модели (staging, marts), макросы, тесты
├── viz/build_charts.py         # графики из витрины
├── reports/                    # сюда падают графики
├── metabase/                   # инструкция по дашбордам
└── docs/erd.md                 # ERD + слои
```

---

## 11. Почему такой стек

- **PostgreSQL** (не ClickHouse/Greenplum) — реляционные данные с FK, объём ~18k строк;
  нативные FK/индексы/представления, понятен Metabase/dbt/Airflow.
- **Airflow CeleryExecutor** (не Local) — нужен отдельный сервис worker, отсюда Celery + Redis.
- **dbt** — слоистые модели, декларативные тесты и документация в одном инструменте.
- **Metabase** (не Superset) — проще в первичной настройке.
