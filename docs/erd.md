# Модель данных — ERD

Диаграмма рендерится на GitHub автоматически (mermaid).

```mermaid
erDiagram
    players ||--o{ deposits    : "player_id"
    players ||--o{ withdrawals : "player_id"
    players ||--o{ games       : "player_id"
    providers_map ||--o{ deposits    : "provider_id"
    providers_map ||--o{ withdrawals : "provider_id"
    providers_map ||--o{ games       : "provider_id"
    providers_map ||--o{ games_map   : "provider_id"
    games_map ||--o{ games : "game_id"

    players {
        int id PK
        date registration_date
        varchar registration_type
        varchar country
    }
    deposits {
        int id PK
        int player_id FK
        date deposit_date
        int provider_id FK
        numeric amount
        varchar currency
    }
    withdrawals {
        int id PK
        int player_id FK
        date withdrawal_date
        int provider_id FK
        numeric amount
        varchar currency
    }
    games {
        int id PK
        int player_id FK
        date game_date
        numeric amount
        varchar currency
        int provider_id FK
        int game_id FK
    }
    currency_rates {
        date date PK
        varchar currency PK
        numeric rate_to_usd
    }
    providers_map {
        int id PK
        varchar provider_name
    }
    games_map {
        int id PK
        varchar game_name
        int provider_id FK
    }
```

## Слои (dbt)

```
raw.*  (CSV 1:1)
  └── staging  stg_*  (типизация, конвертация в USD)  [views]
        └── marts  monthly_summary  (месяц × страна)  [view]
```

`currency_rates` — справочник, подключается в staging-слое через «as-of» джойн
(последний курс с датой ≤ дате транзакции) для устойчивости к пропускам.
