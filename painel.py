"""Leitura, formatação e gráficos do painel da Olist (specs/painel.md).

Este módulo não importa streamlit: app.py monta a página, e o relatório HTML
reaproveita as mesmas funções.

1. LEITURA
   ler(marts) devolve {nome: DataFrame}. Para cada nome roda só
   SELECT * FROM marts.<nome>, e nenhuma outra SQL.
   A conexão é aberta com read_only=True e fechada dentro de ler().
   Motivo: conexão aberta segura o arquivo, e o pipeline.marts não consegue
   gravar com o painel de pé.
   Sem olist.duckdb, ou faltando qualquer um dos doze marts de MARTS, ler()
   levanta MartsFaltando com os nomes, para a página avisar e parar.

2. NENHUM CÁLCULO
   Aqui e em app.py não se agrupa, não se soma, não se tira média, não se
   conta, não se juntam nem se pivotam tabelas, e não se faz conta entre
   colunas. Pode: ordenar, filtrar linhas, pegar as n primeiras, renomear
   coluna e formatar texto.
   Motivo: número novo na tela exige um .sql novo em marts.
   Única exceção: pct_recompra(), porque o mart 05 guarda o complemento.

3. FORMATO
   reais(valor, casas=2)  -> "R$ 1.003.862,14"
   pct(valor, casas=1)    -> "93,2%"
   numero(valor, casas=0) -> "96.470"
   Milhar com ponto, decimal com vírgula, sempre, sem o locale do sistema.
   Motivo: o resultado não pode depender da máquina de quem roda.

4. GRÁFICOS
   Uma função por gráfico: recebe o DataFrame do mart e devolve a figura
   plotly. Título com o número do mart, uma cor só, eixo com unidade.
   Motivo: o relatório HTML reaproveita as mesmas funções.

5. CARTÕES E PERÍODO PADRÃO
   cartoes(dados) devolve os sete pares (rótulo, valor formatado), e
   INICIO_PADRAO/FIM_PADRAO são o período padrão do faturamento.
   Motivo: app.py e relatorio.py mostram os mesmos cartões e o mesmo
   período; morando aqui, não há duas versões para divergir.
"""

from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

BANCO = "olist.duckdb"

MARTS = [
    "vendas_mensais",
    "top_categorias",
    "entrega_no_prazo",
    "nota_por_categoria",
    "recompra",
    "ticket_medio_por_estado",
    "mix_pagamento",
    "nota_por_prazo",
    "vendedores_pareto",
    "tempo_entrega_por_estado",
    "kpis",
    "clientes_por_uf",
]

INICIO_PADRAO = pd.Timestamp("2017-01-01")
FIM_PADRAO = pd.Timestamp("2018-08-01")

COR = "#1f77b4"
ALTURA_LISTA = 600

MESES = {
    1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
    7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez",
}  # fmt: skip


class MartsFaltando(Exception):
    def __init__(self, faltando: list[str], sem_banco: bool = False):
        self.faltando = faltando
        self.sem_banco = sem_banco
        super().__init__(", ".join(faltando))


# ---------------------------------------------------------------- leitura


def ler(marts: list[str]) -> dict[str, pd.DataFrame]:
    if not Path(BANCO).is_file():
        raise MartsFaltando(marts, sem_banco=True)

    dados, faltando = {}, []
    with duckdb.connect(BANCO, read_only=True) as con:
        for nome in marts:
            # Mart faltando é descoberto pelo próprio SELECT *, sem outra SQL.
            try:
                dados[nome] = con.execute(f"SELECT * FROM marts.{nome}").df()
            except duckdb.CatalogException:
                faltando.append(nome)
    if faltando:
        raise MartsFaltando(faltando)
    return dados


def pct_recompra(recompra: pd.DataFrame) -> float:
    # A única conta permitida pela spec: o mart 05 guarda quem comprou uma vez só.
    uma_vez = recompra.loc[recompra["pedidos_por_cliente"] == 1, "pct_clientes"]
    return 100 - uma_vez.iloc[0]


# ---------------------------------------------------------------- formato


def _br(valor: float, casas: int) -> str:
    return f"{valor:,.{casas}f}".translate(str.maketrans(",.", ".,"))


def reais(valor: float, casas: int = 2) -> str:
    return f"R$ {_br(valor, casas)}"


def pct(valor: float, casas: int = 1) -> str:
    return f"{_br(valor, casas)}%"


def numero(valor: float, casas: int = 0) -> str:
    return _br(valor, casas)


def rotulo_mes(mes: pd.Timestamp) -> str:
    return f"{MESES[mes.month]}/{mes.year}"


# ---------------------------------------------------------------- cartões


def cartoes(dados: dict[str, pd.DataFrame]) -> list[tuple[str, str]]:
    kpis = dados["kpis"].iloc[0]
    return [
        (
            "Ticket médio · receita por pedido, sem frete",
            reais(kpis["ticket_medio"]),
        ),
        ("Cancelados · % de todos os pedidos", pct(kpis["pct_cancelados"], 2)),
        ("Peso do frete · % do frete no valor pago", pct(kpis["pct_frete"], 1)),
        (
            "Recompra · % de clientes com 2+ pedidos",
            pct(pct_recompra(dados["recompra"]), 2),
        ),
        (
            "No prazo · % das entregas até a data prevista",
            pct(dados["entrega_no_prazo"]["pct_no_prazo"].iloc[0], 1),
        ),
        (
            "Dias até entregar · média, da compra à entrega",
            numero(kpis["dias_entrega"], 1),
        ),
        ("Nota média · avaliações de 1 a 5", numero(kpis["nota_media"], 2)),
    ]


# ---------------------------------------------------------------- gráficos


def _padrao(fig: go.Figure) -> go.Figure:
    # separators: o plotly usa o 1º caractere como decimal e o 2º como milhar.
    fig.update_layout(separators=",.", margin={"t": 50})
    return fig


def _barras_deitadas(
    df: pd.DataFrame, x: str, y: str, titulo: str, unidade: str, rotulo_y: str
) -> go.Figure:
    # Linhas em ordem decrescente + eixo invertido = maior em cima.
    fig = px.bar(
        df.sort_values(x, ascending=False),
        x=x,
        y=y,
        orientation="h",
        title=titulo,
        labels={x: unidade, y: rotulo_y},
        color_discrete_sequence=[COR],
        height=ALTURA_LISTA,
    )
    fig.update_yaxes(autorange="reversed")
    return _padrao(fig)


def grafico_faturamento(vendas_mensais: pd.DataFrame) -> go.Figure:
    fig = px.line(
        vendas_mensais,
        x="mes",
        y="receita",
        markers=True,
        title="01 · Faturamento mensal",
        labels={"mes": "Mês", "receita": "Receita (R$)"},
        color_discrete_sequence=[COR],
    )
    return _padrao(fig)


def grafico_categorias(top_categorias: pd.DataFrame) -> go.Figure:
    top10 = top_categorias.sort_values("receita", ascending=False).head(10)
    return _barras_deitadas(
        top10,
        "receita",
        "categoria",
        "02 · Receita por categoria (top 10)",
        "Receita (R$)",
        "Categoria",
    )


def grafico_mix_pagamento(mix_pagamento: pd.DataFrame) -> go.Figure:
    fig = px.bar(
        mix_pagamento.sort_values("pct_valor", ascending=False),
        x="tipo",
        y="pct_valor",
        title="07 · Mix de pagamento",
        labels={"tipo": "Tipo de pagamento", "pct_valor": "% do valor pago"},
        color_discrete_sequence=[COR],
        height=ALTURA_LISTA,
    )
    return _padrao(fig)


def grafico_ticket_uf(ticket_medio_por_estado: pd.DataFrame) -> go.Figure:
    return _barras_deitadas(
        ticket_medio_por_estado,
        "ticket_medio",
        "uf",
        "06 · Ticket médio por UF",
        "Ticket médio (R$)",
        "UF do cliente",
    )


def grafico_clientes_uf(clientes_por_uf: pd.DataFrame) -> go.Figure:
    return _barras_deitadas(
        clientes_por_uf,
        "clientes",
        "uf",
        "12 · Clientes por UF",
        "Clientes (pessoas)",
        "UF",
    )


def grafico_nota_categoria(nota_por_categoria: pd.DataFrame) -> go.Figure:
    # Desempate por categoria: com notas iguais, as 10 primeiras são sempre as mesmas.
    piores = nota_por_categoria.sort_values(["posicao_pior", "categoria"]).head(10)
    fig = px.scatter(
        piores,
        x="nota_media",
        y="categoria",
        title="04 · Nota por categoria (10 piores)",
        labels={"nota_media": "Nota média (1 a 5)", "categoria": "Categoria"},
        color_discrete_sequence=[COR],
        height=ALTURA_LISTA,
    )
    fig.update_traces(marker_size=12)
    fig.update_yaxes(autorange="reversed")
    return _padrao(fig)


def grafico_vendedores(vendedores_pareto: pd.DataFrame) -> go.Figure:
    fig = px.line(
        vendedores_pareto.sort_values("posicao"),
        x="posicao",
        y="pct_acumulado",
        title="09 · Concentração de vendedores",
        labels={
            "posicao": "Vendedores, do maior para o menor (posição)",
            "pct_acumulado": "% acumulado da receita",
        },
        color_discrete_sequence=[COR],
        height=ALTURA_LISTA,
    )
    fig.add_hline(y=80, line_dash="dash", line_color=COR)
    return _padrao(fig)
