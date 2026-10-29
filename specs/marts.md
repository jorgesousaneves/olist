CONTEXTO
Pipeline de dados em Python sobre o dataset público da Olist. Esta spec é
a fonte da verdade: não acrescente nada que não esteja escrito aqui. Se
algo estiver ambíguo, pergunte antes de escrever código.

O QUE JÁ EXISTE
- Banco DuckDB olist.duckdb na raiz do projeto.
- O schema refined, criado por pipeline/transformacao.py, com 8 tabelas:
  pedidos, itens_pedido, pagamentos, avaliacoes, clientes, vendedores,
  produtos, traducao_categorias.
- A pasta sql/marts/, com arquivos NN_nome.sql. Cada arquivo tem um único
  SELECT, que pode começar com comentários (--) e com WITH.

O QUE CONSTRUIR
pipeline/marts.py, que roda com:
    uv run python -m pipeline.marts

1. ESCOPO
Lê de refined, escreve no schema marts. Nunca escreve em raw nem em refined.
O schema marts é apagado e recriado a cada execução
(DROP SCHEMA IF EXISTS marts CASCADE).
Motivo: um mart cujo arquivo foi apagado não pode continuar existindo
no banco.

2. UM ARQUIVO, UMA TABELA
Lê todos os sql/marts/*.sql em ordem alfabética.
Nome da tabela = nome do arquivo sem a extensão e sem o prefixo numérico:
  sql/marts/01_vendas_mensais.sql -> marts.vendas_mensais
Executa: CREATE TABLE marts.<nome> AS <conteúdo do arquivo>
Tira espaços e um ponto e vírgula do final do conteúdo, e nada mais.
O Python não altera, não monta e não completa a SQL.
Motivo: a regra de negócio mora inteira no arquivo .sql.

3. SAÍDA NA TELA
Uma linha por mart, com a contagem vinda do banco, milhar com ponto:
  ✓ marts.vendas_mensais        24 linhas
Linha final com o número de marts e o total de linhas.
Os acentos aparecem certos no terminal.

4. ERRO
Antes de tudo: se faltar qualquer uma das 8 tabelas em refined, lista
quais, diz para rodar "uv run python -m pipeline.transformacao" e para.
Se um .sql falhar: mostra o nome do arquivo e a mensagem do DuckDB, não
executa os seguintes e para.
Se um mart voltar com zero linhas: mostra o nome e para.
Motivo: mart vazio é quase sempre um JOIN que não casou, e um dashboard
vazio parece um negócio parado.
Se sql/marts/ não tiver nenhum arquivo: avisa e para.
Antes de executar qualquer SQL: arquivo sem prefixo NN_, ou dois arquivos
que dão o mesmo nome de tabela -> lista quais e para.
Tudo roda numa transação só: se qualquer passo falhar (inclusive o mart
vazio), o schema marts volta a ser o da última execução que deu certo.
Motivo: um schema pela metade quebra o dashboard sem avisar.

CRITÉRIOS DE ACEITE
- Com um arquivo sql/marts/00_teste.sql contendo "SELECT 1 AS x", cria
  marts.teste com 1 linha.
- Apagar o arquivo e rodar de novo faz marts.teste desaparecer.
- Um arquivo com erro de sintaxe para tudo, com o nome do arquivo na
  tela, e marts continua exatamente como estava antes da execução.
- Um arquivo teste.sql, sem prefixo, para antes de executar qualquer SQL.
- Rodar duas vezes seguidas imprime exatamente a mesma coisa.
- Com os 5 marts: vendas_mensais 24, top_categorias 74,
  entrega_no_prazo 1, nota_por_categoria 52, recompra 9. Total: 160.

ENTREGA
1. O código.
2. Uma lista do que você teve que assumir porque não estava nesta spec.