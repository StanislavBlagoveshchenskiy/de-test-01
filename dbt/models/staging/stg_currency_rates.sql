select date::date as date, currency, rate_to_usd from {{ source('raw', 'currency_rates') }}
