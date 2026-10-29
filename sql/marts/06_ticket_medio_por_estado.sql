-- Ticket médio por estado
-- Grão: uma UF do cliente.
-- Ticket = receita de cada pedido válido somada primeiro, média por pedido depois.
WITH receita_pedido AS (
    -- Grão: um pedido válido. (é o seu pedacinho 1)
    SELECT
        p.pedido_id,
        p.cliente_id,
        sum(i.preco) AS receita
    FROM refined.pedidos      AS p
    JOIN refined.itens_pedido AS i ON i.pedido_id = p.pedido_id
    WHERE p.status NOT IN ('unavailable', 'canceled')
    GROUP BY p.pedido_id, p.cliente_id
)
SELECT
    c.uf,
    count(*)                 AS pedidos,
    round(avg(r.receita), 2) AS ticket_medio
FROM receita_pedido   AS r
JOIN refined.clientes AS c ON c.cliente_id = r.cliente_id
GROUP BY c.uf
ORDER BY ticket_medio;