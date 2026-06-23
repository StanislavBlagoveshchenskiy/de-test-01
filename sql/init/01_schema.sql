-- Схема raw и исходные таблицы: типы, первичные и внешние ключи.
-- Применяется один раз при первом старте контейнера Postgres.

CREATE SCHEMA IF NOT EXISTS raw;

-- ---------- Справочники ----------
CREATE TABLE IF NOT EXISTS raw.providers_map (
    id            INTEGER PRIMARY KEY,
    provider_name VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS raw.games_map (
    id          INTEGER PRIMARY KEY,
    game_name   VARCHAR(100) NOT NULL,
    provider_id INTEGER NOT NULL REFERENCES raw.providers_map (id)
);

-- ---------- Игроки ----------
CREATE TABLE IF NOT EXISTS raw.players (
    id                INTEGER PRIMARY KEY,
    registration_date DATE        NOT NULL,
    registration_type VARCHAR(20) NOT NULL,
    country           VARCHAR(2)  NOT NULL
);

-- ---------- Курсы валют (составной PK) ----------
CREATE TABLE IF NOT EXISTS raw.currency_rates (
    date        DATE          NOT NULL,
    currency    VARCHAR(3)    NOT NULL,
    rate_to_usd NUMERIC(18,6) NOT NULL,
    PRIMARY KEY (date, currency)
);

-- ---------- Транзакции ----------
CREATE TABLE IF NOT EXISTS raw.deposits (
    id           INTEGER PRIMARY KEY,
    player_id    INTEGER NOT NULL REFERENCES raw.players (id),
    deposit_date DATE    NOT NULL,
    provider_id  INTEGER NOT NULL REFERENCES raw.providers_map (id),
    amount       NUMERIC(18,2) NOT NULL,
    currency     VARCHAR(3)    NOT NULL
);

CREATE TABLE IF NOT EXISTS raw.withdrawals (
    id              INTEGER PRIMARY KEY,
    player_id       INTEGER NOT NULL REFERENCES raw.players (id),
    withdrawal_date DATE    NOT NULL,
    provider_id     INTEGER NOT NULL REFERENCES raw.providers_map (id),
    amount          NUMERIC(18,2) NOT NULL,
    currency        VARCHAR(3)    NOT NULL
);

CREATE TABLE IF NOT EXISTS raw.games (
    id          INTEGER PRIMARY KEY,
    player_id   INTEGER NOT NULL REFERENCES raw.players (id),
    game_date   DATE    NOT NULL,
    amount      NUMERIC(18,2) NOT NULL,
    currency    VARCHAR(3)    NOT NULL,
    provider_id INTEGER NOT NULL REFERENCES raw.providers_map (id),
    game_id     INTEGER NOT NULL REFERENCES raw.games_map (id)
);

-- Сюда dbt складывает staging-модели и витрину monthly_summary.
CREATE SCHEMA IF NOT EXISTS analytics;
