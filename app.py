"""Página do painel da Olist (specs/painel.md). Rode com: uv run streamlit run app.py"""

import pandas as pd
import streamlit as st

import painel


@st.cache_data
def carregar() -> dict[str, pd.DataFrame]:
    return painel.ler(painel.MARTS)


st.set_page_config(page_title="Olist · visão da operação", layout="wide")

esquerda, direita = st.columns([3, 2])
esquerda.title("Olist · visão da operação")
# O filtro precisa dos dados, e os dados vêm depois do botão; o container
# guarda o lugar do filtro acima do botão.
area_filtro = direita.container()
if direita.button("Recarregar dados"):
    carregar.clear()

try:
    dados = carregar()
except painel.MartsFaltando as erro:
    if erro.sem_banco:
        st.error(
            f"O banco {painel.BANCO} não existe. Rode: uv run python -m pipeline.marts"
        )
    else:
        st.error(
            "Faltando no schema marts: "
            + ", ".join(erro.faltando)
            + ". Rode: uv run python -m pipeline.marts"
        )
    st.stop()

vendas = dados["vendas_mensais"]
with area_filtro:
    inicio, fim = st.select_slider(
        "Período do faturamento",
        options=list(vendas["mes"]),
        value=(painel.INICIO_PADRAO, painel.FIM_PADRAO),
        format_func=painel.rotulo_mes,
    )
    st.caption("os cartões valem para o período inteiro")

# ---------------------------------------------------------------- faixa 1
cartoes = painel.cartoes(dados)
for coluna, (rotulo, valor) in zip(st.columns(len(cartoes)), cartoes):
    coluna.metric(rotulo, valor)

# ---------------------------------------------------------------- faixa 2
no_periodo = vendas[vendas["mes"].between(inicio, fim)]
st.plotly_chart(painel.grafico_faturamento(no_periodo), width="stretch")

# ---------------------------------------------------------------- faixa 3
c1, c2, c3 = st.columns(3)
c1.plotly_chart(painel.grafico_categorias(dados["top_categorias"]), width="stretch")
c2.plotly_chart(painel.grafico_mix_pagamento(dados["mix_pagamento"]), width="stretch")
c3.plotly_chart(
    painel.grafico_ticket_uf(dados["ticket_medio_por_estado"]), width="stretch"
)

# ---------------------------------------------------------------- faixa 4
c1, c2, c3 = st.columns(3)
c1.plotly_chart(painel.grafico_clientes_uf(dados["clientes_por_uf"]), width="stretch")
c2.plotly_chart(
    painel.grafico_nota_categoria(dados["nota_por_categoria"]), width="stretch"
)
c3.plotly_chart(painel.grafico_vendedores(dados["vendedores_pareto"]), width="stretch")
