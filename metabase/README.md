# Metabase — автонастройка и ручной фолбэк

Metabase поднимается вместе со стеком на http://localhost:3000.

## Автоматическая настройка (по умолчанию)

Сервис `metabase-init` (см. docker-compose) после старта Metabase сам:
1. создаёт админа (`MB_ADMIN_EMAIL` / `MB_ADMIN_PASSWORD` из `.env`,
   по умолчанию `admin@example.com` / `Metabase123!`);
2. подключает источник данных **PostgreSQL** (host `postgres`, port `5432`,
   db `casino`);
3. собирает дашборд **«Casino overview»** с двумя графиками поверх
   `analytics.monthly_summary`:
   - «Динамика по месяцам (USD)» — line;
   - «Распределение по странам (USD)» — bar.

Повторный запуск безопасен: скрипт логинится под существующим админом, видит уже
подключённую БД и собранный дашборд и ничего не дублирует. Перед сборкой дашборда
он дожидается появления витрины `analytics.monthly_summary` (её создаёт DAG), чтобы
дашборд был сразу с данными; если витрина ещё не готова — структура всё равно
создаётся и наполнится после прогона DAG. Если сборка дашборда почему-то не прошла,
подключение к БД остаётся, а дашборд можно собрать вручную (ниже).

Логи провижининга: `docker compose logs metabase-init`.

## Ручная настройка (фолбэк)

Если нужно собрать дашборд руками:
1. Войдите в Metabase, при необходимости создайте админа.
2. Settings → Admin → Databases → Add database → **PostgreSQL**:
   - Host: `postgres`, Port: `5432`, Database: `casino`,
     User/Password: из `.env`.
3. После синхронизации появится `analytics.monthly_summary`. Постройте:
   - **Line**: X = `month`, Y = `total_deposits_usd`, `total_withdrawals_usd`, `total_bets_usd`.
   - **Bar**: X = `country`, Y = суммы `total_*_usd` (group by country).
4. Добавьте оба вопроса на один Dashboard.

> Metabase хранит свои метаданные в H2 на named-volume `metabase-data`
> (просто и надёжно для тестового). Полный сброс — `docker compose down -v`.
