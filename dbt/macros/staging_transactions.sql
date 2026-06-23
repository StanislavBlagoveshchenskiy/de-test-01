{#
    Общая сборка staging-модели для транзакций (deposits/withdrawals/games):
    приводим дату к txn_date, тянем курс на дату транзакции через lateral-джойн
    (последний курс с date <= txn_date — заодно прикрывает дни без курса),
    считаем amount_usd общим макросом to_usd.

    extra_select — доп. колонки конкретного потока, например ', t.game_id'.
#}
{% macro staging_transactions(source_table, date_column, extra_select='') %}
with txn as (
    select * from {{ source('raw', source_table) }}
)
select
    t.id,
    t.player_id,
    t.{{ date_column }}::date                  as txn_date,
    t.provider_id,
    t.amount::numeric(18,2)                    as amount,
    t.currency,
    r.rate_to_usd,
    round({{ to_usd('t.amount', 'r.rate_to_usd') }}, 2) as amount_usd
    {{ extra_select }}
from txn t
left join lateral (
    select cr.rate_to_usd
    from {{ source('raw', 'currency_rates') }} cr
    where cr.currency = t.currency
      and cr.date <= t.{{ date_column }}
    order by cr.date desc
    limit 1
) r on true
{% endmacro %}
