-- Singular-тест: зерно витрины (month, country) уникально (нет дублей).
select month, country, count(*) as n
from {{ ref('monthly_summary') }}
group by month, country
having count(*) > 1
