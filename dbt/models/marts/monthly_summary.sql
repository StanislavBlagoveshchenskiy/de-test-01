{{ config(materialized='view') }}

{#
    Витрина monthly_summary (view), гранулярность месяц × страна.
    Три потока сводим в один union, джойним к players ради страны и
    агрегируем разом через filter — без тройного джойна.
#}

with deposits as (
    select date_trunc('month', txn_date)::date as month, player_id, amount_usd, 'deposit' as kind
    from {{ ref('stg_deposits') }}
),
withdrawals as (
    select date_trunc('month', txn_date)::date as month, player_id, amount_usd, 'withdrawal' as kind
    from {{ ref('stg_withdrawals') }}
),
games as (
    select date_trunc('month', txn_date)::date as month, player_id, amount_usd, 'bet' as kind
    from {{ ref('stg_games') }}
),
unioned as (
    select * from deposits
    union all
    select * from withdrawals
    union all
    select * from games
),
joined as (
    select
        u.month,
        p.country,
        u.kind,
        u.amount_usd
    from unioned u
    inner join {{ ref('stg_players') }} p on p.id = u.player_id
)
select
    month,
    country,
    round(coalesce(sum(amount_usd) filter (where kind = 'deposit'),    0), 2) as total_deposits_usd,
    round(coalesce(sum(amount_usd) filter (where kind = 'withdrawal'), 0), 2) as total_withdrawals_usd,
    round(coalesce(sum(amount_usd) filter (where kind = 'bet'),        0), 2) as total_bets_usd,
    round(
        coalesce(sum(amount_usd) filter (where kind = 'deposit'),    0)
      - coalesce(sum(amount_usd) filter (where kind = 'withdrawal'), 0)
    , 2) as net_usd,
    count(*) filter (where kind = 'deposit')    as deposits_cnt,
    count(*) filter (where kind = 'withdrawal') as withdrawals_cnt,
    count(*) filter (where kind = 'bet')        as bets_cnt
from joined
group by month, country
order by month, country
