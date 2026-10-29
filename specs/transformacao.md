CONTEXTO
Pipeline de dados em Python sobre o dataset público da Olist.
Esta spec é a fonte da verdade: não acrescente nada que não esteja
escrito aqui. Se algo estiver ambíguo, pergunte antes de escrever código.

★ O QUE JÁ EXISTE
- Banco DuckDB olist.duckdb na raiz do projeto.
- Schema raw, criado pela ingestão (pipeline/ingestao.py): 9 tabelas
  com o nome original dos arquivos (raw.olist_orders_dataset etc.),
  todas as colunas VARCHAR, campo vazio como NULL.

★ O QUE CONSTRUIR
pipeline/transformacao.py, que roda com:
    uv run python -m pipeline.transformacao

1. ESCOPO
Lê de raw, escreve em refined. Nunca escreve em raw.
Tabelas que entram (8): pedidos, itens, pagamentos, avaliações,
clientes, vendedores, produtos, tradução das categorias.
Motivo: 7 delas são usadas pelos meus indicadores. Vendedores entra
porque é pequena (3.095 linhas) e pode servir para indicadores novos.
Fica de fora: geolocalização. Nenhum indicador usa, tem 1.000.163
linhas e é o desafio de casa. Não se limpa o que ninguém vai ler.

2. NOMES
Tabelas e colunas traduzidas para português, minúsculo, sem acento,
"_" no lugar de espaço. Nenhuma coluna fora do mapa; nenhuma descartada.
Motivo: facilitar os JOINs da aula 3, que vou digitar de memória.

pedidos  (raw.olist_orders_dataset)
  order_id -> pedido_id
  customer_id -> cliente_id
  order_status -> status
  order_purchase_timestamp -> data_compra
  order_approved_at -> data_aprovacao
  order_delivered_carrier_date -> data_envio
  order_delivered_customer_date -> data_entrega
  order_estimated_delivery_date -> data_entrega_prevista

itens_pedido  (raw.olist_order_items_dataset)
  order_id -> pedido_id
  order_item_id -> item_seq
  product_id -> produto_id
  seller_id -> vendedor_id
  shipping_limit_date -> data_limite_envio
  price -> preco
  freight_value -> frete

pagamentos  (raw.olist_order_payments_dataset)
  order_id -> pedido_id
  payment_sequential -> pagamento_seq
  payment_type -> tipo
  payment_installments -> parcelas
  payment_value -> valor

avaliacoes  (raw.olist_order_reviews_dataset)
  review_id -> avaliacao_id
  order_id -> pedido_id
  review_score -> nota
  review_comment_title -> titulo
  review_comment_message -> comentario
  review_creation_date -> data_criacao
  review_answer_timestamp -> data_resposta

clientes  (raw.olist_customers_dataset)
  customer_id -> cliente_id
  customer_unique_id -> cliente_unico_id
  customer_zip_code_prefix -> cep_prefixo
  customer_city -> cidade
  customer_state -> uf

vendedores  (raw.olist_sellers_dataset)
  seller_id -> vendedor_id
  seller_zip_code_prefix -> cep_prefixo
  seller_city -> cidade
  seller_state -> uf

produtos  (raw.olist_products_dataset)
  product_id -> produto_id
  product_category_name -> categoria
  product_name_lenght -> tamanho_nome
  product_description_lenght -> tamanho_descricao
  product_photos_qty -> qtd_fotos
  product_weight_g -> peso_g
  product_length_cm -> comprimento_cm
  product_height_cm -> altura_cm
  product_width_cm -> largura_cm

traducao_categorias  (raw.product_category_name_translation)
  product_category_name -> categoria
  product_category_name_english -> categoria_en

3. TIPOS
Regra: se não faço conta com a coluna, ela continua texto.

TIMESTAMP (data com hora de verdade), formato '%Y-%m-%d %H:%M:%S':
  data_compra, data_aprovacao, data_envio, data_entrega,
  data_limite_envio, data_resposta
  Motivo: a hora existe e um dia pode ser útil.

DATE (só o dia):
  data_entrega_prevista
    Motivo: a hora é 00:00:00 em todas as 99.441 linhas.
  data_criacao
    Motivo: a hora é 00:00:00 em 99.139 de 99.224 linhas. As outras 85
    são 01:00:00 nos dias de início do horário de verão (16/10/2016 e
    15/10/2017), quando a meia-noite não existiu. Não é hora de verdade.

DECIMAL(10,2) (dinheiro): preco, frete, valor
  Motivo: DOUBLE não guarda centavos com exatidão
  (0.1 + 0.2 = 0.30000000000000004), e a soma do dinheiro tem que fechar.

INTEGER (contagens e medidas):
  item_seq, pagamento_seq, parcelas, nota, tamanho_nome,
  tamanho_descricao, qtd_fotos, peso_g, comprimento_cm,
  altura_cm, largura_cm

VARCHAR (texto): todo o resto, inclusive todos os _id e o cep_prefixo.
  Motivo: são identificadores, ninguém faz conta com eles. Como número,
  o CEP perderia o zero: 23.995 clientes têm CEP começando com 0.

★ A conversão é feita em SQL, pelo DuckDB, sem passar pelo pandas.
  Motivo: o pandas não tem tipo DECIMAL e transformaria dinheiro em
  número aproximado sem avisar.

Para virar DATE, a data é lida primeiro no formato completo com hora,
para que um valor fora do padrão faça o programa parar.

4. CONVERSÃO QUE FALHA
Para tudo. Mostra a tabela, a coluna e um exemplo do valor que não
converteu, e encerra com erro.
Nunca usar try_strptime, TRY_CAST ou nada que transforme falha em vazio.
Motivo: pedidos já tem 2.965 vazios verdadeiros (pedidos não entregues).
Um vazio fabricado por falha de conversão ficaria igual a eles, e
ninguém conseguiria separar os dois nunca mais.

5. DUPLICATAS
Chave de cada tabela:
  pedidos              pedido_id
  itens_pedido         pedido_id + item_seq
  pagamentos           pedido_id + pagamento_seq
  avaliacoes           avaliacao_id + pedido_id
                       (avaliacao_id sozinho repete: a mesma avaliação
                        aparece em mais de um pedido)
  clientes             cliente_id
  vendedores           vendedor_id
  produtos             produto_id
  traducao_categorias  categoria
Linha inteira repetida: mantém uma e conta quantas saíram.
Mesma chave com conteúdo diferente: para tudo e mostra as linhas em
conflito.
Motivo: as tabelas da Olist não têm coluna que diga qual versão é a
mais recente; escolher uma seria escolher em silêncio. Hoje há zero
duplicatas, então essa regra não custa nada.
Limite: se a raw passar a guardar histórico com data_carga, esta regra
vira ROW_NUMBER() OVER (PARTITION BY chave ORDER BY data_carga DESC)
e fica a versão mais recente.

As linhas idênticas são removidas antes da conversão de tipo, ainda
como texto ('29.9' e '29.90' viram o mesmo número depois).
A conferência de chave com conteúdo diferente é feita pelo programa,
em toda execução, depois de remover as linhas idênticas.

6. VAZIOS
Nenhuma linha é apagada por ter vazio, e nenhum vazio é preenchido.
Motivo: o vazio é informação. Dos 2.965 pedidos sem data de entrega,
quase todos não foram entregues de verdade (1.107 a caminho, 619
cancelados, 609 indisponíveis...). Apagar sumiria com os cancelamentos.
Os 610 produtos sem categoria continuam sem categoria: como mostrar
isso no gráfico é decisão da aula 3.
Estranhezas que ficam como estão (são fato, não erro de leitura):
- 8 pedidos "delivered" sem data de entrega
- 14 pedidos "delivered" sem data de aprovação
- 775 pedidos sem nenhum item

7. SAÍDA NA TELA
No final, o programa diz SUCESSO ou NÃO SUCESSO.
SUCESSO só se, em todas as tabelas:
- linhas que saem = linhas que entram − duplicatas idênticas removidas;
- a quantidade de vazios em cada coluna é a mesma antes e depois.
Se der NÃO SUCESSO, mostra qual tabela e o que ficou diferente.
Motivo: quero saber na hora se deu certo; e "certo" quer dizer
que nenhuma linha sumiu e nenhum vazio foi fabricado.

★ REEXECUÇÃO E ERRO (iguais à ingestão)
A tabela é apagada e criada de novo a cada execução.
Se faltar alguma tabela de entrada em raw, o programa diz quais faltam,
manda rodar "uv run python -m pipeline.ingestao" e para sem gravar nada.

A conferência roda antes de confirmar a gravação. Se der NÃO SUCESSO,
nada é gravado e a refined da execução anterior fica intacta.
Motivo: refined com dado errado é lida pela aula 3 sem ninguém perceber.

★ CRITÉRIOS DE ACEITE
- Rodar uma vez mostra SUCESSO. Rodar de novo mostra SUCESSO de novo.
- Oito tabelas em refined, com estas linhas: pedidos 99.441,
  itens_pedido 112.650, pagamentos 103.886, avaliacoes 99.224,
  clientes 99.441, vendedores 3.095, produtos 32.951,
  traducao_categorias 71. Total: 550.759.
- refined.pedidos: data_aprovacao 160, data_envio 1.783 e
  data_entrega 2.965 vazios.
- refined.produtos: categoria com 610 vazios.
- DESCRIBE refined.pedidos mostra TIMESTAMP em data_compra,
  data_aprovacao, data_envio e data_entrega, e DATE em
  data_entrega_prevista.
- sum(preco) em refined.itens_pedido é igual a
  sum(CAST(price AS DECIMAL(10,2))) em raw, centavo por centavo.
- cep_prefixo mantém o zero da frente: '01151', não 1151.
- refined.avaliacoes: titulo 87.656 e comentario 58.247 vazios.
- sum(preco) em refined.itens_pedido = 13.591.643,70.

ENTREGA
1. O código.
2. Uma lista do que você teve que assumir porque não estava nesta spec.
