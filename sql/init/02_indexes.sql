-- Вторичные индексы под джойны и фильтры витрины
-- (PK-индексы Postgres создаёт сам).

-- Джойн транзакций к players и агрегация по дате.
CREATE INDEX IF NOT EXISTS ix_deposits_player_id    ON raw.deposits    (player_id);
CREATE INDEX IF NOT EXISTS ix_deposits_date         ON raw.deposits    (deposit_date);
CREATE INDEX IF NOT EXISTS ix_deposits_currency     ON raw.deposits    (currency);

CREATE INDEX IF NOT EXISTS ix_withdrawals_player_id ON raw.withdrawals (player_id);
CREATE INDEX IF NOT EXISTS ix_withdrawals_date      ON raw.withdrawals (withdrawal_date);
CREATE INDEX IF NOT EXISTS ix_withdrawals_currency  ON raw.withdrawals (currency);

CREATE INDEX IF NOT EXISTS ix_games_player_id       ON raw.games       (player_id);
CREATE INDEX IF NOT EXISTS ix_games_date            ON raw.games       (game_date);
CREATE INDEX IF NOT EXISTS ix_games_currency        ON raw.games       (currency);
CREATE INDEX IF NOT EXISTS ix_games_game_id         ON raw.games       (game_id);

-- Фильтр/группировка витрины по стране.
CREATE INDEX IF NOT EXISTS ix_players_country       ON raw.players     (country);

-- Джойн курса по (currency, date) и фолбэк «последний известный курс».
CREATE INDEX IF NOT EXISTS ix_rates_currency_date   ON raw.currency_rates (currency, date);
