# Makefile — удобные цели для Mac/Linux.
# На Windows make «из коробки» нет → в README продублированы сырые docker compose команды.

.PHONY: help up down restart logs trigger test viz ps clean

help:           ## показать список целей
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-12s %s\n", $$1, $$2}'

up:             ## собрать образы и поднять всю инфраструктуру
	docker compose up -d --build

down:           ## остановить и удалить контейнеры
	docker compose down

clean:          ## down + удалить volumes (полный сброс)
	docker compose down -v

restart:        ## перезапустить
	docker compose restart

ps:             ## статус сервисов
	docker compose ps

logs:           ## хвост логов всех сервисов
	docker compose logs -f --tail=100

trigger:        ## вручную запустить DAG
	docker compose exec airflow-scheduler airflow dags trigger etl_monthly_summary

test:           ## прогнать dbt-тесты внутри worker'а
	docker compose exec airflow-worker /opt/dbt-venv/bin/dbt test --project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt

viz:            ## пересобрать графики
	docker compose exec airflow-worker python /opt/airflow/viz/build_charts.py
