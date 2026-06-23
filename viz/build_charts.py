"""
Графики по витрине analytics.monthly_summary -> reports/:
  - monthly_dynamics — депозиты/выводы/ставки по месяцам;
  - by_country       — то же в разрезе стран.

PNG рисуем matplotlib'ом, интерактивный HTML — plotly.
Подключение к Postgres берём из DBT_* (с дефолтами для локалки).
"""
from __future__ import annotations

import os

import pandas as pd
from sqlalchemy import create_engine

REPORTS_DIR = os.environ.get("REPORTS_DIR", "/opt/airflow/reports")


def get_engine():
    user = os.environ.get("DBT_USER", "postgres")
    password = os.environ.get("DBT_PASSWORD", "postgres")
    host = os.environ.get("DBT_HOST", "postgres")
    port = os.environ.get("DBT_PORT", "5432")
    dbname = os.environ.get("DBT_DBNAME", "casino")
    return create_engine(f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}")


def load_summary(engine) -> pd.DataFrame:
    df = pd.read_sql("SELECT * FROM analytics.monthly_summary ORDER BY month, country", engine)
    df["month"] = pd.to_datetime(df["month"])
    return df


def chart_monthly_dynamics(df: pd.DataFrame) -> None:
    """График 1: динамика депозитов/выводов/ставок по месяцам (сумма по всем странам)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import plotly.graph_objects as go

    by_month = (
        df.groupby("month")[["total_deposits_usd", "total_withdrawals_usd", "total_bets_usd"]]
        .sum()
        .reset_index()
        .sort_values("month")
    )

    # --- matplotlib PNG ---
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(by_month["month"], by_month["total_deposits_usd"], marker="o", label="Депозиты, USD")
    ax.plot(by_month["month"], by_month["total_withdrawals_usd"], marker="o", label="Выводы, USD")
    ax.plot(by_month["month"], by_month["total_bets_usd"], marker="o", label="Ставки, USD")
    ax.set_title("Динамика депозитов, выводов и ставок по месяцам (USD)")
    ax.set_xlabel("Месяц")
    ax.set_ylabel("Сумма, USD")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(os.path.join(REPORTS_DIR, "monthly_dynamics.png"), dpi=120)
    plt.close(fig)

    # --- plotly HTML ---
    pfig = go.Figure()
    for col, name in [
        ("total_deposits_usd", "Депозиты"),
        ("total_withdrawals_usd", "Выводы"),
        ("total_bets_usd", "Ставки"),
    ]:
        pfig.add_trace(go.Scatter(x=by_month["month"], y=by_month[col], mode="lines+markers", name=name))
    pfig.update_layout(title="Динамика по месяцам (USD)", xaxis_title="Месяц", yaxis_title="USD")
    pfig.write_html(os.path.join(REPORTS_DIR, "monthly_dynamics.html"))


def chart_by_country(df: pd.DataFrame) -> None:
    """График 2: распределение сумм по странам (за весь период)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import plotly.graph_objects as go

    by_country = (
        df.groupby("country")[["total_deposits_usd", "total_withdrawals_usd", "total_bets_usd"]]
        .sum()
        .reset_index()
        .sort_values("total_deposits_usd", ascending=False)
    )

    # --- matplotlib PNG (сгруппированные столбцы) ---
    import numpy as np
    x = np.arange(len(by_country))
    width = 0.27
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(x - width, by_country["total_deposits_usd"], width, label="Депозиты")
    ax.bar(x, by_country["total_withdrawals_usd"], width, label="Выводы")
    ax.bar(x + width, by_country["total_bets_usd"], width, label="Ставки")
    ax.set_title("Распределение по странам (USD, весь период)")
    ax.set_xlabel("Страна")
    ax.set_ylabel("Сумма, USD")
    ax.set_xticks(x)
    ax.set_xticklabels(by_country["country"])
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(REPORTS_DIR, "by_country.png"), dpi=120)
    plt.close(fig)

    # --- plotly HTML ---
    pfig = go.Figure()
    for col, name in [
        ("total_deposits_usd", "Депозиты"),
        ("total_withdrawals_usd", "Выводы"),
        ("total_bets_usd", "Ставки"),
    ]:
        pfig.add_trace(go.Bar(x=by_country["country"], y=by_country[col], name=name))
    pfig.update_layout(barmode="group", title="Распределение по странам (USD)",
                       xaxis_title="Страна", yaxis_title="USD")
    pfig.write_html(os.path.join(REPORTS_DIR, "by_country.html"))


def main() -> None:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    engine = get_engine()
    df = load_summary(engine)
    if df.empty:
        raise SystemExit("monthly_summary пуста — сначала отработал ли ETL/dbt?")
    chart_monthly_dynamics(df)
    chart_by_country(df)
    print(f"[viz] графики сохранены в {REPORTS_DIR}: "
          "monthly_dynamics.png/html, by_country.png/html")


if __name__ == "__main__":
    main()
