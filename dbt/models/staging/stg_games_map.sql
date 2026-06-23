select id, game_name, provider_id from {{ source('raw', 'games_map') }}
