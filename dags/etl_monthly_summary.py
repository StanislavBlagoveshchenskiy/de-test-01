"""
Месячный ETL: CSV -> raw -> dbt (staging + monthly_summary) -> dbt-тесты -> графики.

Загрузка идемпотентна (ON CONFLICT DO NOTHING), повторный запуск не плодит дубли.
Расписание месячное, без catchup.
"""
from __future__ import annotations

import os
from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

DATA_DIR = os.environ.get("DATA_DIR", "/opt/airflow/data")
DBT_DIR = os.environ.get("DBT_DIR", "/opt/airflow/dbt")
# dbt живёт в отдельном venv, чтобы его зависимости не конфликтовали с Airflow.
DBT_BIN = os.environ.get("DBT_BIN", "dbt")

# Грузим в порядке FK: справочники и players раньше транзакций.
# (таблица, колонки, ключ для ON CONFLICT)
LOAD_SPEC = [
    ("providers_map",  ["id", "provider_name"],                                              ["id"]),
    ("games_map",      ["id", "game_name", "provider_id"],                                    ["id"]),
    ("players",        ["id", "registration_date", "registration_type", "country"],          ["id"]),
    ("currency_rates", ["date", "currency", "rate_to_usd"],                                   ["date", "currency"]),
    ("deposits",       ["id", "player_id", "deposit_date", "provider_id", "amount", "currency"],    ["id"]),
    ("withdrawals",    ["id", "player_id", "withdrawal_date", "provider_id", "amount", "currency"], ["id"]),
    ("games",          ["id", "player_id", "game_date", "amount", "currency", "provider_id", "game_id"], ["id"]),
]


def load_raw_csv(**_):
    """Грузит все CSV в схему raw. psycopg2 импортируем внутри, чтобы DAG
    парсился и там, где драйвера ещё нет."""
    import csv

    import psycopg2
    from psycopg2.extras import execute_values

    conn = psycopg2.connect(
        host=os.environ["DBT_HOST"],
        port=int(os.environ.get("DBT_PORT", "5432")),
        user=os.environ["DBT_USER"],
        password=os.environ["DBT_PASSWORD"],
        dbname=os.environ["DBT_DBNAME"],
    )
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            for table, columns, conflict in LOAD_SPEC:
                path = os.path.join(DATA_DIR, f"{table}.csv")
                with open(path, newline="", encoding="utf-8") as fh:
                    reader = csv.reader(fh)
                    header = next(reader)  # пропускаем заголовок
                    rows = [tuple(r) for r in reader]

                cols_sql = ", ".join(columns)
                conflict_sql = ", ".join(conflict)
                sql = (
                    f"INSERT INTO raw.{table} ({cols_sql}) VALUES %s "
                    f"ON CONFLICT ({conflict_sql}) DO NOTHING"
                )
                execute_values(cur, sql, rows, page_size=1000)
                print(f"[load] raw.{table}: предложено {len(rows)} строк (дубликаты игнорируются)")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


default_args = {
    "owner": "data-engineering",
    "retries": 1,
}

with DAG(
    dag_id="etl_monthly_summary",
    description="CSV → raw → dbt (monthly_summary) → tests → charts",
    start_date=datetime(2024, 1, 1),
    schedule="@monthly",
    catchup=False,
    is_paused_upon_creation=False,  # чтобы не включать руками после деплоя
    default_args=default_args,
    tags=["etl", "dbt", "monthly_summary"],
) as dag:

    load_csv = PythonOperator(
        task_id="load_csv",
        python_callable=load_raw_csv,
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"cd {DBT_DIR} && {DBT_BIN} run --profiles-dir {DBT_DIR}",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {DBT_DIR} && {DBT_BIN} test --profiles-dir {DBT_DIR}",
    )

    build_charts = BashOperator(
        task_id="build_charts",
        bash_command="python /opt/airflow/viz/build_charts.py",
    )

    load_csv >> dbt_run >> dbt_test >> build_charts
