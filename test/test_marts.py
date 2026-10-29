"""Testes de pipeline/marts.py (specs/marts.md) e do SQL dos marts 01 e 03."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb

from pipeline import marts

SQL_DO_PROJETO = Path(__file__).resolve().parent.parent / "sql" / "marts"


def preparar(tmp_path, monkeypatch, arquivos):
    """Banco com as 8 tabelas de refined (vazias) e uma pasta sql/marts inventada."""
    banco = tmp_path / "olist.duckdb"
    pasta = tmp_path / "sql" / "marts"
    pasta.mkdir(parents=True)
    for nome, sql in arquivos.items():
        (pasta / nome).write_text(sql, encoding="utf-8")
    with duckdb.connect(str(banco)) as con:
        con.execute("CREATE SCHEMA refined")
        for tabela in marts.TABELAS_ORIGEM:
            con.execute(f"CREATE TABLE refined.{tabela} (id INTEGER)")
    # RAIZ também: as mensagens de erro mostram a pasta relativa a ela.
    monkeypatch.setattr(marts, "RAIZ", tmp_path)
    monkeypatch.setattr(marts, "BANCO", banco)
    monkeypatch.setattr(marts, "PASTA_SQL", pasta)
    return banco, pasta


def tabelas_marts(banco):
    with duckdb.connect(str(banco), read_only=True) as con:
        return con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'marts' ORDER BY table_name"
        ).fetchall()


def test_um_arquivo_vira_uma_tabela_sem_o_prefixo(tmp_path, monkeypatch):
    banco, _ = preparar(tmp_path, monkeypatch, {"00_teste.sql": "SELECT 1 AS x;"})
    assert marts.main() == 0
    with duckdb.connect(str(banco), read_only=True) as con:
        assert con.execute("SELECT x FROM marts.teste").fetchall() == [(1,)]


def test_arquivo_apagado_faz_o_mart_sumir_na_execucao_seguinte(tmp_path, monkeypatch):
    banco, pasta = preparar(
        tmp_path,
        monkeypatch,
        {"01_fica.sql": "SELECT 1 AS x", "02_sai.sql": "SELECT 2 AS x"},
    )
    assert marts.main() == 0
    (pasta / "02_sai.sql").unlink()
    assert marts.main() == 0
    assert tabelas_marts(banco) == [("fica",)]


def test_arquivo_sem_prefixo_para_antes_de_executar(tmp_path, monkeypatch):
    banco, _ = preparar(
        tmp_path,
        monkeypatch,
        {"01_ok.sql": "SELECT 1 AS x", "teste.sql": "SELECT 1 AS x"},
    )
    assert marts.main() == 1
    # Nem o 01_ok.sql, que é válido, chegou a rodar.
    assert tabelas_marts(banco) == []


def test_dois_arquivos_com_o_mesmo_nome_de_tabela_param_antes_de_executar(
    tmp_path, monkeypatch
):
    banco, _ = preparar(
        tmp_path,
        monkeypatch,
        {"01_igual.sql": "SELECT 1 AS x", "02_igual.sql": "SELECT 2 AS x"},
    )
    assert marts.main() == 1
    assert tabelas_marts(banco) == []


def test_mart_vazio_encerra_e_deixa_o_schema_como_estava(tmp_path, monkeypatch):
    banco, pasta = preparar(tmp_path, monkeypatch, {"01_ok.sql": "SELECT 1 AS x"})
    assert marts.main() == 0
    # Um JOIN que não casou: zero linhas.
    (pasta / "02_vazio.sql").write_text("SELECT 1 AS x WHERE false", encoding="utf-8")
    assert marts.main() == 1
    assert tabelas_marts(banco) == [("ok",)]


def test_sql_com_erro_encerra_e_deixa_o_schema_como_estava(tmp_path, monkeypatch):
    banco, pasta = preparar(tmp_path, monkeypatch, {"01_ok.sql": "SELECT 1 AS x"})
    assert marts.main() == 0
    (pasta / "02_quebrado.sql").write_text("SELEC 1", encoding="utf-8")
    assert marts.main() == 1
    assert tabelas_marts(banco) == [("ok",)]


def test_pasta_sem_arquivo_sql_encerra_com_erro(tmp_path, monkeypatch):
    banco, _ = preparar(tmp_path, monkeypatch, {})
    assert marts.main() == 1
    assert tabelas_marts(banco) == []


def test_tabela_faltando_em_refined_encerra_com_erro(tmp_path, monkeypatch):
    banco, _ = preparar(tmp_path, monkeypatch, {"01_ok.sql": "SELECT 1 AS x"})
    with duckdb.connect(str(banco)) as con:
        con.execute("DROP TABLE refined.vendedores")
    assert marts.main() == 1
    assert tabelas_marts(banco) == []


def test_sem_banco_todas_as_tabelas_de_refined_faltam(tmp_path, monkeypatch):
    monkeypatch.setattr(marts, "BANCO", tmp_path / "olist.duckdb")
    assert marts.tabelas_faltando() == marts.TABELAS_ORIGEM


def test_tira_um_ponto_e_virgula_e_os_espacos_do_final(tmp_path):
    arquivo = tmp_path / "01_x.sql"
    arquivo.write_text("-- comentário\nSELECT 1 ;  \n", encoding="utf-8")
    assert marts.ler_select(arquivo) == "-- comentário\nSELECT 1"


def test_milhar_com_ponto():
    assert marts.formatar(1234567) == "1.234.567"


# ------------------------------------------------- SQL dos marts 01 e 03


def rodar_sql(tmp_path, arquivo, pedidos, itens=()):
    """Roda um .sql do projeto sobre refined.pedidos e refined.itens_pedido inventadas."""
    with duckdb.connect(str(tmp_path / "olist.duckdb")) as con:
        con.execute("CREATE SCHEMA refined")
        con.execute(
            "CREATE TABLE refined.pedidos (pedido_id VARCHAR, status VARCHAR, "
            "data_compra TIMESTAMP, data_entrega TIMESTAMP, data_entrega_prevista DATE)"
        )
        con.execute(
            "CREATE TABLE refined.itens_pedido "
            "(pedido_id VARCHAR, item_seq INTEGER, preco DECIMAL(10,2))"
        )
        con.executemany("INSERT INTO refined.pedidos VALUES (?, ?, ?, ?, ?)", pedidos)
        if itens:
            con.executemany("INSERT INTO refined.itens_pedido VALUES (?, ?, ?)", itens)
        return con.execute(marts.ler_select(SQL_DO_PROJETO / arquivo)).fetchall()


def test_pedido_com_dois_itens_conta_uma_vez(tmp_path):
    vendas = rodar_sql(
        tmp_path,
        "01_vendas_mensais.sql",
        pedidos=[("p1", "delivered", "2017-03-10 10:00:00", None, None)],
        itens=[
            ("p1", 1, Decimal("10.00")),  # dois itens no mesmo pedido
            ("p1", 2, Decimal("15.50")),
        ],
    )
    assert vendas == [(date(2017, 3, 1), 1, Decimal("25.50"))]


def test_cancelado_fica_fora_da_receita(tmp_path):
    vendas = rodar_sql(
        tmp_path,
        "01_vendas_mensais.sql",
        pedidos=[
            ("p1", "delivered", "2017-03-10 10:00:00", None, None),
            ("p2", "canceled", "2017-03-11 10:00:00", None, None),  # fica fora
            ("p3", "unavailable", "2017-03-12 10:00:00", None, None),  # fica fora
        ],
        itens=[
            ("p1", 1, Decimal("10.00")),
            ("p2", 1, Decimal("99.00")),
            ("p3", 1, Decimal("50.00")),
        ],
    )
    assert [(pedidos, receita) for _, pedidos, receita in vendas] == [
        (1, Decimal("10.00"))
    ]


def test_entrega_no_dia_previsto_a_tarde_esta_no_prazo(tmp_path):
    prazo = rodar_sql(
        tmp_path,
        "03_entrega_no_prazo.sql",
        pedidos=[
            # Chegou às 15h do dia previsto: no prazo.
            (
                "p1",
                "delivered",
                "2017-03-01 10:00:00",
                "2017-03-10 15:00:00",
                "2017-03-10",
            ),
            # Chegou no dia seguinte ao previsto: atrasado.
            (
                "p2",
                "delivered",
                "2017-03-01 10:00:00",
                "2017-03-11 09:00:00",
                "2017-03-10",
            ),
            # Entregue sem data de entrega: fora do denominador.
            ("p3", "delivered", "2017-03-01 10:00:00", None, "2017-03-10"),
            # Não entregue: fora do denominador.
            ("p4", "shipped", "2017-03-01 10:00:00", None, "2017-03-10"),
        ],
    )
    entregues, no_prazo, atrasados, pct_no_prazo = prazo[0]
    assert (entregues, no_prazo, atrasados) == (2, 1, 1)
    assert pct_no_prazo == 50.0
