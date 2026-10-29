PEDIDOS
- 99.441 pedidos; 160 sem aprovação, 1.783 sem envio, 2.965 sem entrega
- Os sem entrega são, quase todos, pedidos que não chegaram (a caminho,
  cancelados, indisponíveis). O vazio é informação, não erro.
- Estranhos: 8 "delivered" sem data de entrega; 14 "delivered" sem aprovação.
- Nenhum pedido repetido: 99.441 linhas, 99.441 order_id diferentes.
ITENS
- 112.650 itens em 98.666 pedidos (um pedido pode ter vários itens).
- Chave = order_id + order_item_id. Nenhum item repetido.
- 775 pedidos não têm nenhum item.
- Cuidado: remover duplicata usando só order_id apagaria 13.984 itens.
DATAS
- Formato: ano-mês-dia hora:min:seg (%Y-%m-%d %H:%M:%S), 19 caracteres.
- Testado em todas as 99.441 linhas: 0 falhas.
CEP
- 23.995 clientes têm CEP começando com 0. CEP fica texto.
CLIENTES
- 99.441 customer_id (um por pedido), mas 96.096 pessoas (customer_unique_id).
- Para contar clientes de verdade, usar customer_unique_id.

DATAS
- order_estimated_delivery_date: hora sempre 00:00:00 → na prática é só data.
AVALIAÇÕES
- data_criacao: hora 00:00:00 em 99.139 linhas; 85 com 01:00:00 por
  causa do horário de verão. Na prática é só data.