{#
  Generic-тест: значения в колонке не отрицательны.
  Использование:  tests: [non_negative]
#}
{% test non_negative(model, column_name) %}
select {{ column_name }}
from {{ model }}
where {{ column_name }} < 0
{% endtest %}
