# Pipeline de dados · Olist

Pipeline em Python e SQL sobre o dataset público da Olist, um e-commerce brasileiro (2016 a 2018, cerca de 1,5 milhão de registros). Ele leva os CSVs de origem até um dashboard, em três camadas, com validação em cada etapa e testes unitários.

Construído com **spec-driven development**: cada etapa começa com uma spec das decisões e do motivo de cada uma ([`specs/`](specs/)), e o código é gerado e conferido contra ela.

## O que ele responde

| Pergunta | Resposta |
|---|---|
| Quanto a Olist vendeu? | R$ 13.494.400,74 em 98.199 pedidos válidos com itens |
| Quanto vale um pedido típico? | Ticket médio de R$ 137,42 |
| Os clientes voltam? | Só 3,04% das pessoas compraram mais de uma vez |
| A entrega chega no prazo? | 93,2% dos pedidos entregues |
| O atraso derruba a nota? | Sim: nota 2,27 para atrasados e 4,29 para os no prazo; 62,4% dos atrasados dão nota 1 ou 2 |
| As vendas são concentradas? | 540 dos 3.053 vendedores fazem 80% da receita |
| Onde a entrega demora mais? | RR, com 29,3 dias em média; SP é o mais rápido, com 8,7 |

## Arquitetura

```
raw/*.csv.gz ──► raw ──────────► refined ─────────► marts ─────────► dashboard
                 1.550.922 linhas  550.759 linhas      12 tabelas       app.py
                 como chegou       tipado e validado   uma por pergunta relatorio.html
```

| Camada | O que faz | Código |
|---|---|---|
| **raw** (bronze) | Copia os 9 CSVs sem mudar nada: tudo como texto, vazio continua vazio | [`pipeline/ingestao.py`](pipeline/ingestao.py) |
| **refined** (silver) | Converte tipos, traduz nomes, confere duplicatas e garante que nenhuma linha sumiu e nenhum vazio foi fabricado | [`pipeline/transformacao.py`](pipeline/transformacao.py) |
| **marts** (gold) | Um arquivo SQL por indicador; o Python só executa | [`sql/marts/`](sql/marts/) e [`pipeline/marts.py`](pipeline/marts.py) |
| **consumo** | Lê só os marts, sem nenhum cálculo na tela | [`app.py`](app.py), [`relatorio.py`](relatorio.py) e [`painel.py`](painel.py) |

Os princípios por trás de cada decisão estão em [`ARQUITETURA.md`](ARQUITETURA.md).

## O que é uma linha de cada tabela (o grão)

| Tabela em refined | Uma linha é | Chave | Linhas |
|---|---|---|---|
| `pedidos` | um pedido | `pedido_id` | 99.441 |
| `itens_pedido` | um item de um pedido | `pedido_id`, `item_seq` | 112.650 |
| `pagamentos` | um pagamento de um pedido | `pedido_id`, `pagamento_seq` | 103.886 |
| `avaliacoes` | uma avaliação de um pedido | `avaliacao_id`, `pedido_id` | 99.224 |
| `clientes` | um cliente **por pedido** (a pessoa é `cliente_unico_id`: 96.096) | `cliente_id` | 99.441 |
| `vendedores` | um vendedor | `vendedor_id` | 3.095 |
| `produtos` | um produto | `produto_id` | 32.951 |
| `traducao_categorias` | uma categoria | `categoria` | 71 |

A geolocalização (1.000.163 linhas) fica só na raw: nenhum indicador usa.

## Os indicadores (marts)

| Arquivo | Pergunta |
|---|---|
| `01_vendas_mensais` | Quanto vendemos por mês? |
| `02_top_categorias` | Quais categorias mais vendem? |
| `03_entrega_no_prazo` | Quanto chegou no prazo? |
| `04_nota_por_categoria` | Que nota cada categoria recebe? |
| `05_recompra` | Quantos clientes voltaram a comprar? |
| `06_ticket_medio_por_estado` | Qual o ticket médio por estado? |
| `07_mix_pagamento` | Como os clientes pagam? |
| `08_nota_por_prazo` | O atraso derruba a nota? |
| `09_vendedores_pareto` | Quantos vendedores fazem 80% da receita? |
| `10_tempo_entrega_por_estado` | Quantos dias leva a entrega por estado? |
| `11_kpis` | Os cartões do topo do dashboard |
| `12_clientes_por_uf` | Quantas pessoas compram de cada estado? |

Cada arquivo começa com o grão do resultado escrito em comentário.

## Como rodar do zero

Precisa do [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                  # instala Python e dependências
uv run python -m pipeline.ingestao       # CSV → raw
uv run python -m pipeline.transformacao  # raw → refined
uv run python -m pipeline.marts          # refined → marts
```

Cada etapa termina dizendo SUCESSO ou mostrando o que deu errado, e só grava se tudo der certo. Rodar de novo dá o mesmo resultado.

```bash
uv run streamlit run app.py   # dashboard em http://localhost:8501
uv run python relatorio.py    # o mesmo painel em relatorio.html, para abrir sem Python
uv run pytest --cov           # 63 testes, 95% de coverage
uv run python ui.py           # notebook SQL do DuckDB em http://localhost:4213
```

O banco (`olist.duckdb`) aceita um escritor por vez: feche o `ui.py` (Ctrl+C) antes de rodar o pipeline.

## Stack

Python 3.12, uv, DuckDB, pandas, Streamlit, Plotly e pytest. A IA (Claude Code) acessa o banco por MCP, em somente leitura.

## Onde a IA errou, e como eu descobri

A IA escreveu a maior parte do código Python, a partir das minhas specs. Conferir o que ela entregou foi parte do trabalho:

- **Respondeu sem consultar o banco.** A primeira resposta "pelo MCP" veio do terminal, porque o MCP ainda não estava conectado. Descobri ao exigir que ela usasse só o MCP e mostrasse a SQL.
- **Afirmou uma configuração errada.** Disse que o servidor MCP abria o banco em modo de escrita e sugeriu uma opção extra. A ajuda do próprio servidor (`--help`) mostrou que o padrão já é somente leitura.
- **Generalizou a partir de uma amostra.** Testou o formato de data em 2 das 5 colunas e concluiu que todas convertiam; afirmou que uma data "nunca tem hora" olhando 5 linhas. Pedi a conferência nas 99.441 linhas e nas colunas que faltavam.
- **Deixou uma regra da spec fora do código.** A spec mandava parar quando uma chave se repete com conteúdo diferente. Ela conferiu isso à mão durante o teste, mas o SQL não fazia a conferência. Pedi que ela rodasse em toda execução.
- **Gravava quando a validação falhava.** Na transformação, um NÃO SUCESSO deixava as tabelas gravadas. Mudei a spec para conferir antes do COMMIT e desfazer tudo em caso de falha.
- **Acrescentou uma decisão que não estava na spec.** Abriu o banco do `ui.py` em somente leitura, o que quebrou o notebook do DuckDB ("localmemdb does not exist"). A lição: ler a lista do que a IA assumiu antes de aceitar.
- **Coverage alto no lugar errado.** Com 93% de coverage, nenhum teste conferia o NÃO SUCESSO da transformação, a regra que mais protege a refined. O teste foi escrito depois, e provado: ele falha quando o ROLLBACK vira COMMIT.

Quase sempre a descoberta veio do mesmo hábito: **contar as linhas antes e depois** e comparar com um número que eu tinha contado antes, sem a IA.

## Limitações

- O pipeline recria tudo a cada execução, porque o dataset é uma foto parada. Com uma fonte que muda, a raw passaria a guardar histórico com a data da carga.
- Não há orquestrador: as etapas rodam pela linha de comando.
- As validações de dado rodam dentro de cada etapa; não há uma ferramenta dedicada de qualidade de dados, como dbt ou Soda.

## Fonte e créditos

- Dados: [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), no Kaggle, sob licença [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).
- Projeto desenvolvido seguindo o curso [Pipeline Olist](https://ckoliveiraa.github.io/pipeline-olist/).
