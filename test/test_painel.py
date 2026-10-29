"""Testes de painel.py (specs/painel.md), com marts inventados em tmp_path."""

import duckdb
import pandas as pd
import pytest

import painel


def test_reais_com_milhar_ponto_e_decimal_virgula():
    assert painel.reais(1234567.5) == "R$ 1.234.567,50"


def test_reais_sem_centavos():
    assert painel.reais(1234.4, 0) == "R$ 1.234"


def test_pct_com_uma_casa_por_padrao():
    assert painel.pct(12.34) == "12,3%"


def test_pct_com_duas_casas_e_milhar():
    assert painel.pct(1234.5, 2) == "1.234,50%"


def test_numero_sem_casas_por_padrao():
    assert painel.numero(1234567) == "1.234.567"


def test_numero_com_casas_e_negativo():
    assert painel.numero(-1500.25, 2) == "-1.500,25"


def test_rotulo_do_mes_em_portugues():
    assert painel.rotulo_mes(pd.Timestamp("2017-02-01")) == "fev/2017"


# ---------------------------------------------------------------- cartões


def test_recompra_e_o_complemento_de_quem_comprou_uma_vez():
    recompra = pd.DataFrame(
        {
            "pedidos_por_cliente": [1, 2],  # 90% compraram uma vez só
            "pct_clientes": [90.0, 10.0],
        }
    )
    assert painel.pct_recompra(recompra) == 10.0


def test_cartoes_formatam_os_valores_dos_marts():
    dados = {
        "kpis": pd.DataFrame(
            {
                "ticket_medio": [100.5],
                "pct_cancelados": [1.25],
                "pct_frete": [10.0],
                "dias_entrega": [7.5],
                "nota_media": [4.5],
            }
        ),
        "recompra": pd.DataFrame({"pedidos_por_cliente": [1], "pct_clientes": [75.0]}),
        "entrega_no_prazo": pd.DataFrame({"pct_no_prazo": [80.0]}),
    }
    valores = [valor for _, valor in painel.cartoes(dados)]
    assert valores == ["R$ 100,50", "1,25%", "10,0%", "25,00%", "80,0%", "7,5", "4,50"]


# ---------------------------------------------------------------- gráficos


def pontos(figura):
    return len(figura.data[0].x)


def test_grafico_faturamento_tem_um_ponto_por_mes():
    vendas = pd.DataFrame(
        {"mes": pd.to_datetime(["2017-01-01", "2017-02-01", "2017-03-01"]),
         "receita": [10.0, 20.0, 30.0]}
    )  # fmt: skip
    assert pontos(painel.grafico_faturamento(vendas)) == 3


def test_grafico_categorias_tem_uma_barra_por_categoria():
    categorias = pd.DataFrame({"categoria": ["a", "b"], "receita": [5.0, 9.0]})
    assert pontos(painel.grafico_categorias(categorias)) == 2


def test_grafico_categorias_mostra_so_as_dez_maiores():
    categorias = pd.DataFrame(
        {
            "categoria": [f"c{i}" for i in range(12)],
            "receita": [float(i) for i in range(12)],
        }
    )
    assert pontos(painel.grafico_categorias(categorias)) == 10


def test_grafico_mix_pagamento_tem_uma_barra_por_tipo():
    mix = pd.DataFrame({"tipo": ["boleto", "voucher"], "pct_valor": [60.0, 40.0]})
    assert pontos(painel.grafico_mix_pagamento(mix)) == 2


def test_grafico_ticket_uf_tem_uma_barra_por_uf():
    ticket = pd.DataFrame({"uf": ["SP", "RJ", "MG"], "ticket_medio": [1.0, 2.0, 3.0]})
    assert pontos(painel.grafico_ticket_uf(ticket)) == 3


def test_grafico_clientes_uf_tem_uma_barra_por_uf():
    clientes = pd.DataFrame({"uf": ["SP", "RJ"], "clientes": [3, 1]})
    assert pontos(painel.grafico_clientes_uf(clientes)) == 2


def test_grafico_nota_categoria_tem_um_ponto_por_categoria():
    notas = pd.DataFrame(
        {
            "categoria": ["a", "b", "c"],
            "nota_media": [3.5, 4.0, 4.5],
            "posicao_pior": [1, 2, 3],
        }
    )
    assert pontos(painel.grafico_nota_categoria(notas)) == 3


def test_grafico_vendedores_tem_um_ponto_por_vendedor():
    pareto = pd.DataFrame(
        {"posicao": [1, 2, 3, 4], "pct_acumulado": [50.0, 80.0, 95.0, 100.0]}
    )
    assert pontos(painel.grafico_vendedores(pareto)) == 4


# ---------------------------------------------------------------- leitura


def criar_banco(pasta, marts):
    with duckdb.connect(str(pasta / "olist.duckdb")) as con:
        con.execute("CREATE SCHEMA marts")
        for nome in marts:
            con.execute(
                f"CREATE TABLE marts.{nome} AS SELECT 1 AS x UNION ALL SELECT 2"
            )


def test_ler_devolve_um_dataframe_por_mart(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    criar_banco(tmp_path, ["um", "dois"])
    dados = painel.ler(["um", "dois"])
    assert list(dados) == ["um", "dois"]
    assert list(dados["um"]["x"]) == [1, 2]


def test_ler_fecha_a_conexao(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    criar_banco(tmp_path, ["um"])
    painel.ler(["um"])
    # Com uma conexão somente leitura ainda aberta, o DuckDB recusaria esta de escrita.
    with duckdb.connect("olist.duckdb") as con:
        con.execute("CREATE TABLE marts.novo AS SELECT 1 AS x")
        assert con.execute("SELECT x FROM marts.novo").fetchall() == [(1,)]


def test_ler_lista_todos_os_marts_que_faltam(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    criar_banco(tmp_path, ["um"])
    with pytest.raises(painel.MartsFaltando) as erro:
        painel.ler(["um", "dois", "tres"])
    assert erro.value.faltando == ["dois", "tres"]
    assert erro.value.sem_banco is False


def test_ler_sem_banco_avisa_que_o_banco_nao_existe(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(painel.MartsFaltando) as erro:
        painel.ler(["um"])
    assert erro.value.sem_banco is True
    assert not (tmp_path / "olist.duckdb").exists()
