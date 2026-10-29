"""Testes de relatorio.py (specs/relatorio.md), com os doze marts inventados em tmp_path."""

from datetime import datetime

import duckdb

import relatorio

# Uma ou duas linhas por mart, só com as colunas que o painel lê.
MARTS = {
    "vendas_mensais": """
        SELECT * FROM (VALUES
            (DATE '2016-12-01', 100.0),  -- antes do período padrão: fica fora
            (DATE '2017-01-01', 200.0),
            (DATE '2018-08-01', 300.0)
        ) AS t(mes, receita)""",
    "top_categorias": "SELECT 'livros' AS categoria, 50.0 AS receita",
    "entrega_no_prazo": "SELECT 80.0 AS pct_no_prazo",
    "nota_por_categoria": "SELECT 'livros' AS categoria, 4.5 AS nota_media, 1 AS posicao_pior",
    "recompra": "SELECT 1 AS pedidos_por_cliente, 75.0 AS pct_clientes",
    "ticket_medio_por_estado": "SELECT 'SP' AS uf, 100.0 AS ticket_medio",
    "mix_pagamento": "SELECT 'boleto' AS tipo, 100.0 AS pct_valor",
    "nota_por_prazo": "SELECT 'no_prazo' AS situacao",
    "vendedores_pareto": "SELECT 1 AS posicao, 100.0 AS pct_acumulado",
    "tempo_entrega_por_estado": "SELECT 'SP' AS uf",
    "kpis": """
        SELECT 100.5 AS ticket_medio, 1.25 AS pct_cancelados, 10.0 AS pct_frete,
               7.5 AS dias_entrega, 4.5 AS nota_media""",
    "clientes_por_uf": "SELECT 'SP' AS uf, 3 AS clientes",
}


def preparar(tmp_path, monkeypatch, sem=None):
    monkeypatch.chdir(tmp_path)
    with duckdb.connect("olist.duckdb") as con:
        con.execute("CREATE SCHEMA marts")
        for nome, select in MARTS.items():
            if nome != sem:
                con.execute(f"CREATE TABLE marts.{nome} AS {select}")


def relogio(hora):
    class Relogio:
        @staticmethod
        def now():
            return hora

    return Relogio


def gerar(monkeypatch, hora):
    monkeypatch.setattr(relatorio, "datetime", relogio(hora))
    assert relatorio.main() == 0
    return relatorio.ARQUIVO.read_text(encoding="utf-8")


def test_gera_o_arquivo_dentro_da_pasta_de_onde_se_roda(tmp_path, monkeypatch):
    preparar(tmp_path, monkeypatch)
    assert relatorio.main() == 0
    assert (tmp_path / "relatorio.html").is_file()


def test_cartoes_mostram_os_valores_formatados(tmp_path, monkeypatch):
    preparar(tmp_path, monkeypatch)
    html = gerar(monkeypatch, datetime(2026, 10, 25, 14, 3))
    for valor in ["R$ 100,50", "1,25%", "10,0%", "25,00%", "80,0%", "7,5", "4,50"]:
        assert f'<div class="valor">{valor}</div>' in html


def test_rodape_diz_quando_o_arquivo_foi_gerado(tmp_path, monkeypatch):
    preparar(tmp_path, monkeypatch)
    html = gerar(monkeypatch, datetime(2026, 10, 25, 14, 3))
    assert "<footer>Dados de 25/10/2026 14:03</footer>" in html


def test_rodar_duas_vezes_muda_so_o_rodape(tmp_path, monkeypatch):
    preparar(tmp_path, monkeypatch)
    primeira = gerar(monkeypatch, datetime(2026, 10, 25, 14, 3)).splitlines()
    segunda = gerar(monkeypatch, datetime(2026, 10, 26, 9, 30)).splitlines()
    assert len(primeira) == len(segunda)
    diferentes = [(a, b) for a, b in zip(primeira, segunda) if a != b]
    assert diferentes == [
        (
            "<footer>Dados de 25/10/2026 14:03</footer>",
            "<footer>Dados de 26/10/2026 09:30</footer>",
        )
    ]


def test_faturamento_mostra_o_periodo_padrao_no_titulo(tmp_path, monkeypatch):
    preparar(tmp_path, monkeypatch)
    html = gerar(monkeypatch, datetime(2026, 10, 25, 14, 3))
    assert (
        "01 \\u00b7 Faturamento mensal \\u00b7 jan\\u002f2017 a ago\\u002f2018" in html
    )


def test_biblioteca_do_plotly_vem_do_cdn_uma_vez_so(tmp_path, monkeypatch):
    preparar(tmp_path, monkeypatch)
    html = gerar(monkeypatch, datetime(2026, 10, 25, 14, 3))
    assert html.count("cdn.plot.ly") == 1


def test_cada_grafico_tem_id_fixo(tmp_path, monkeypatch):
    preparar(tmp_path, monkeypatch)
    html = gerar(monkeypatch, datetime(2026, 10, 25, 14, 3))
    for numero in range(1, 8):
        assert f'id="g{numero:02d}"' in html


def test_mart_faltando_encerra_sem_gerar_o_arquivo(tmp_path, monkeypatch):
    preparar(tmp_path, monkeypatch, sem="kpis")
    assert relatorio.main() == 1
    assert not (tmp_path / "relatorio.html").exists()


def test_sem_banco_encerra_sem_gerar_o_arquivo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert relatorio.main() == 1
    assert not (tmp_path / "relatorio.html").exists()
