-- Tempo de entrega por estado: quantos dias da compra até a entrega?
-- Grão: uma UF do cliente.
-- Denominador igual ao do mart 03: delivered com data de entrega.
-- Conta da compra (não do envio): é o tempo que o cliente espera.
SELECT
    c.uf,
    count(*) AS entregues,
    round(avg(date_diff('day', p.data_compra, p.data_entrega)), 1) AS dias_medio,
    median(date_diff('day', p.data_compra, p.data_entrega))        AS dias_mediana
FROM refined.pedidos  AS p
JOIN refined.clientes AS c ON c.cliente_id = p.cliente_id
WHERE p.status = 'delivered'
  AND p.data_entrega IS NOT NULL
GROUP BY c.uf
ORDER BY dias_medio;