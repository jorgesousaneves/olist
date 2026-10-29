"""Gera relatorio.html com as mesmas faixas do app.py (specs/relatorio.md).

Rode com: uv run python relatorio.py
"""

import sys
from datetime import datetime
from html import escape
from pathlib import Path

import painel

ARQUIVO = Path("relatorio.html")
TITULO = "Olist · visão da operação"

ESTILO = """
body { font-family: system-ui, sans-serif; margin: 24px; color: #222; background: #fff; }
h1 { margin: 0 0 16px; }
.cartoes { display: grid; grid-template-columns: repeat(7, 1fr); gap: 12px; margin-bottom: 16px; }
.cartao { border: 1px solid #ddd; border-radius: 8px; padding: 12px; }
.rotulo { font-size: 13px; color: #555; }
.valor { font-size: 28px; margin-top: 4px; }
.tres { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
footer { margin-top: 24px; font-size: 13px; color: #555; }
@media (max-width: 900px) {
  .cartoes { grid-template-columns: repeat(2, 1fr); }
  .tres { grid-template-columns: 1fr; }
}
"""


def html_cartoes(cartoes: list[tuple[str, str]]) -> str:
    itens = [
        f'<div class="cartao"><div class="rotulo">{escape(rotulo)}</div>'
        f'<div class="valor">{escape(valor)}</div></div>'
        for rotulo, valor in cartoes
    ]
    return '<div class="cartoes">' + "".join(itens) + "</div>"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")

    try:
        dados = painel.ler(painel.MARTS)
    except painel.MartsFaltando as erro:
        if erro.sem_banco:
            print(f"ERRO: o banco {painel.BANCO} não existe.")
        else:
            print(f"ERRO: faltando no schema marts: {', '.join(erro.faltando)}")
        print("Rode: uv run python -m pipeline.marts")
        return 1

    vendas = dados["vendas_mensais"]
    no_periodo = vendas[vendas["mes"].between(painel.INICIO_PADRAO, painel.FIM_PADRAO)]
    faturamento = painel.grafico_faturamento(no_periodo)
    periodo = (
        f"{painel.rotulo_mes(painel.INICIO_PADRAO)} a "
        f"{painel.rotulo_mes(painel.FIM_PADRAO)}"
    )
    faturamento.update_layout(title_text=f"{faturamento.layout.title.text} · {periodo}")

    # Mesma ordem do app.py: faixa 2, depois as três colunas das faixas 3 e 4.
    figuras = [
        faturamento,
        painel.grafico_categorias(dados["top_categorias"]),
        painel.grafico_mix_pagamento(dados["mix_pagamento"]),
        painel.grafico_ticket_uf(dados["ticket_medio_por_estado"]),
        painel.grafico_clientes_uf(dados["clientes_por_uf"]),
        painel.grafico_nota_categoria(dados["nota_por_categoria"]),
        painel.grafico_vendedores(dados["vendedores_pareto"]),
    ]
    graficos = [
        figura.to_html(
            full_html=False,
            include_plotlyjs="cdn" if posicao == 1 else False,
            div_id=f"g{posicao:02d}",
        )
        for posicao, figura in enumerate(figuras, start=1)
    ]

    gerado = datetime.now().strftime("%d/%m/%Y %H:%M")
    pagina = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{TITULO}</title>
<style>{ESTILO}</style>
</head>
<body>
<h1>{TITULO}</h1>
{html_cartoes(painel.cartoes(dados))}
{graficos[0]}
<div class="tres">{"".join(graficos[1:4])}</div>
<div class="tres">{"".join(graficos[4:7])}</div>
<footer>Dados de {gerado}</footer>
</body>
</html>
"""
    ARQUIVO.write_text(pagina, encoding="utf-8")

    tamanho = ARQUIVO.stat().st_size / 1024
    print(f"{ARQUIVO.resolve()}  {painel.numero(tamanho, 1)} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
