select
    id,
    registration_date::date as registration_date,
    registration_type,
    country
from {{ source('raw', 'players') }}
