select id, provider_name from {{ source('raw', 'providers_map') }}
