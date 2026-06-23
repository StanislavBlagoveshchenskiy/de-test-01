# Airflow + dbt в одном образе.
# dbt держим в отдельном venv: его пины (sqlalchemy и т.п.) конфликтуют
# с Airflow, если ставить в общий питон.
ARG AIRFLOW_VERSION=2.9.3
ARG PYTHON_VERSION=3.11
FROM apache/airflow:${AIRFLOW_VERSION}-python${PYTHON_VERSION}

ARG AIRFLOW_VERSION
ARG PYTHON_VERSION

# Зависимости для тасков load_csv / build_charts, с official constraints.
COPY requirements-airflow.txt /tmp/requirements-airflow.txt
RUN pip install --no-cache-dir -r /tmp/requirements-airflow.txt \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

# dbt в отдельный venv. Создаём из-под root: airflow-юзеру нельзя писать в /opt.
# После установки возвращаем каталог airflow и переключаемся обратно.
ENV DBT_VENV=/opt/dbt-venv
USER root
RUN python -m venv ${DBT_VENV} \
 && ${DBT_VENV}/bin/pip install --no-cache-dir --upgrade pip \
 && ${DBT_VENV}/bin/pip install --no-cache-dir \
        "dbt-core==1.9.1" \
        "dbt-postgres==1.9.0" \
 && chown -R airflow:0 ${DBT_VENV}
USER airflow

# dbt прокидываем в DAG через DBT_BIN.
ENV DBT_BIN=${DBT_VENV}/bin/dbt
