CONTEXTO
Projeto de dados em Python com o dataset público da Olist. Esta spec é a
fonte da verdade: não acrescente nada que não esteja escrito aqui. Se algo
estiver ambíguo, pergunte antes de escrever código.

★ O QUE CONSTRUIR
Um arquivo pipeline/ingestao.py, que roda com:
    uv run python -m pipeline.ingestao
Ele lê as 9 planilhas da pasta raw/ e grava no banco DuckDB olist.duckdb,
na raiz do projeto, dentro do schema "raw". Usa pandas para ler.

1. NOMES DAS TABELAS
Cada tabela tem o mesmo nome do arquivo, sem o ".csv.gz".
olist_orders_dataset.csv.gz               -> olist_orders_dataset
olist_order_items_dataset.csv.gz          -> olist_order_items_dataset
olist_order_payments_dataset.csv.gz       -> olist_order_payments_dataset
olist_order_reviews_dataset.csv.gz        -> olist_order_reviews_dataset
olist_customers_dataset.csv.gz            -> olist_customers_dataset
olist_sellers_dataset.csv.gz              -> olist_sellers_dataset
olist_products_dataset.csv.gz             -> olist_products_dataset
product_category_name_translation.csv.gz  -> product_category_name_translation
olist_geolocation_dataset.csv.gz          -> olist_geolocation_dataset
Motivo: manter igual à origem, para saber de que arquivo veio cada tabela.

2. OS DADOS VÊM IGUAIS À FONTE
Nada pode ser mudado na ingestão:
- nenhuma linha apagada, nem as repetidas
- nenhum campo vazio preenchido (vazio continua vazio)
- nenhum nome de coluna alterado
- nenhum valor corrigido
- nenhuma conversão de tipo: tudo entra como texto, inclusive datas e
  números (para o CEP não perder o zero da frente)
Motivo: preciso saber o que veio da Olist e o que eu mudei. As correções
acontecem na silver, onde cada uma é uma decisão escrita.
- só o campo vazio vira nulo; textos como "NA", "N/a" e "null"
  continuam como texto
- o caractere invisível (BOM) do começo do arquivo é removido, para
  o nome da coluna chegar igual ao da planilha

3. RODAR DE NOVO
A tabela é apagada e criada de novo a cada execução. Rodar 10 vezes dá o
mesmo resultado que rodar 1.
Motivo: o banco fica sempre igual à planilha da pasta raw/. Posso errar e
rodar de novo sem estragar nada.
Limite: não guarda o passado. Serve porque as planilhas da Olist são uma
foto parada. Se a fonte passar a mudar e eu precisar de histórico, a
ingestão passa a acrescentar linhas com a data da carga.

4. LEITURA DO ARQUIVO
- Acentos: chegam inteiros, igual à planilha ("São Paulo" continua
  "São Paulo"). Normalizar acento é tarefa da silver.
- Arquivo comprimido: o programa lê o .csv.gz direto, sem descompactar.
Motivo: a raw guarda o original.

5. ERRO
Antes de copiar qualquer coisa, o programa confere se as 9 planilhas estão
na pasta raw/. Se faltar alguma, ele para, diz qual está faltando e não
copia nenhuma.
Motivo: copiar 8 de 9 em silêncio gera um resultado errado que parece certo.
Se uma planilha der erro no meio da cópia, nenhuma tabela é alterada:
ou copia as 9, ou nenhuma.
Arquivos a mais na pasta raw/ são ignorados.

6. SAÍDA NA TELA
No final, o programa diz SUCESSO ou NÃO SUCESSO. Para decidir, ele compara
a quantidade de linhas de cada tabela, contada no banco, com a quantidade
esperada abaixo. Se der NÃO SUCESSO, mostra qual tabela ficou diferente e
quantas linhas ela tem.
Esperado:
  olist_customers_dataset              99441
  olist_geolocation_dataset          1000163
  olist_order_items_dataset           112650
  olist_order_payments_dataset        103886
  olist_order_reviews_dataset          99224
  olist_orders_dataset                 99441
  olist_products_dataset               32951
  olist_sellers_dataset                 3095
  product_category_name_translation       71
Motivo: quero saber na hora se deu certo, sem conferir número por número.
Limite: se a planilha mudar, atualizo esta lista.
Antes do resultado final, mostra uma linha para cada tabela carregada.

★ CRITÉRIOS DE ACEITE
- Rodar uma vez mostra SUCESSO.
- Rodar duas vezes seguidas mostra SUCESSO de novo (nada duplicou).
- Tirar uma planilha da pasta faz o programa parar sem copiar nada.
- No banco, o CEP dos clientes mantém o zero da frente.

★ ENTREGA
1. O código.
2. Uma lista do que você teve que assumir porque não estava nesta spec.