"""Testes de pipeline/transformacao.py (specs/transformacao.md), com raw inventada em tmp_path."""

from decimal import Decimal

import duckdb

from pipeline import transformacao

# Colunas de cada tabela de raw, na ordem da planilha. Tudo VARCHAR, como a ingestão deixa.
COLUNAS_RAW = {
    "olist_orders_dataset": [
        "order_id", "customer_id", "order_status", "order_purchase_timestamp",
        "order_approved_at", "order_delivered_carrier_date",
        "order_delivered_customer_date", "order_estimated_delivery_date",
    ],
    "olist_order_items_dataset": [
        "order_id", "order_item_id", "product_id", "seller_id",
        "shipping_limit_date", "price", "freight_value",
    ],
    "olist_order_payments_dataset": [
        "order_id", "payment_sequential", "payment_type",
        "payment_installments", "payment_value",
    ],
    "olist_order_reviews_dataset": [
        "review_id", "order_id", "review_score", "review_comment_title",
        "review_comment_message", "review_creation_date", "review_answer_timestamp",
    ],
    "olist_customers_dataset": [
        "customer_id", "customer_unique_id", "customer_zip_code_prefix",
        "customer_city", "customer_state",
    ],
    "olist_sellers_dataset": [
        "seller_id", "seller_zip_code_prefix", "seller_city", "seller_state",
    ],
    "olist_products_dataset": [
        "product_id", "product_category_name", "product_name_lenght",
        "product_description_lenght", "product_photos_qty", "product_weight_g",
        "product_length_cm", "product_height_cm", "product_width_cm",
    ],
    "product_category_name_translation": [
        "product_category_name", "product_category_name_english",
    ],
}  # fmt: skip

# Pedido entregue: todas as datas preenchidas.
PEDIDO = (
    "p1", "c1", "delivered", "2017-01-05 10:00:00", "2017-01-05 11:00:00",
    "2017-01-06 09:00:00", "2017-01-10 15:00:00", "2017-01-12 00:00:00",
)  # fmt: skip
ITEM = ("p1", "1", "pr1", "v1", "2017-01-07 00:00:00", "29.9", "5.1")


def preparar(tmp_path, monkeypatch, linhas, sem=None):
    """Cria as 8 tabelas de raw (vazias, se não houver linhas para elas)."""
    banco = tmp_path / "olist.duckdb"
    monkeypatch.setattr(transformacao, "BANCO", banco)
    with duckdb.connect(str(banco)) as con:
        con.execute("CREATE SCHEMA raw")
        for tabela, colunas in COLUNAS_RAW.items():
            if tabela == sem:
                continue
            definicao = ", ".join(f"{c} VARCHAR" for c in colunas)
            con.execute(f"CREATE TABLE raw.{tabela} ({definicao})")
            for linha in linhas.get(tabela, []):
                marcas = ", ".join("?" for _ in colunas)
                con.execute(f"INSERT INTO raw.{tabela} VALUES ({marcas})", list(linha))
    return banco


def consultar(banco, sql):
    with duckdb.connect(str(banco), read_only=True) as con:
        return con.execute(sql).fetchall()


def tabelas_refined(banco):
    return consultar(
        banco,
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'refined'",
    )


def test_duplicata_exata_sai(tmp_path, monkeypatch):
    # A mesma linha duas vezes: fica uma.
    banco = preparar(tmp_path, monkeypatch, {"olist_orders_dataset": [PEDIDO, PEDIDO]})
    assert transformacao.main() == 0
    assert consultar(banco, "SELECT count(*) FROM refined.pedidos") == [(1,)]


def test_datas_viram_timestamp_e_a_prevista_vira_date(tmp_path, monkeypatch):
    banco = preparar(tmp_path, monkeypatch, {"olist_orders_dataset": [PEDIDO]})
    transformacao.main()
    tipos = {
        coluna: tipo
        for coluna, tipo, *_ in consultar(banco, "DESCRIBE refined.pedidos")
    }
    assert tipos["data_compra"] == "TIMESTAMP"
    assert tipos["data_entrega"] == "TIMESTAMP"
    assert tipos["data_entrega_prevista"] == "DATE"


def test_dinheiro_vira_decimal_com_centavos_exatos(tmp_path, monkeypatch):
    # '29.9' na planilha vira 29.90 exato, sem aproximação de ponto flutuante.
    banco = preparar(tmp_path, monkeypatch, {"olist_order_items_dataset": [ITEM]})
    transformacao.main()
    tipos = {
        coluna: tipo
        for coluna, tipo, *_ in consultar(banco, "DESCRIBE refined.itens_pedido")
    }
    assert tipos["preco"] == "DECIMAL(10,2)"
    assert consultar(banco, "SELECT preco, frete FROM refined.itens_pedido") == [
        (Decimal("29.90"), Decimal("5.10"))
    ]


def test_cep_continua_texto_com_o_zero(tmp_path, monkeypatch):
    cliente = ("c1", "u1", "01151", "sao paulo", "SP")  # CEP com zero à esquerda
    banco = preparar(tmp_path, monkeypatch, {"olist_customers_dataset": [cliente]})
    transformacao.main()
    assert consultar(banco, "SELECT cep_prefixo FROM refined.clientes") == [("01151",)]


def test_data_vazia_continua_vazia(tmp_path, monkeypatch):
    # Pedido a caminho: sem data de entrega.
    a_caminho = PEDIDO[:6] + (None,) + PEDIDO[7:]
    banco = preparar(tmp_path, monkeypatch, {"olist_orders_dataset": [a_caminho]})
    assert transformacao.main() == 0
    assert consultar(banco, "SELECT data_entrega FROM refined.pedidos") == [(None,)]


def test_valor_que_nao_converte_encerra_com_erro_sem_virar_nulo(tmp_path, monkeypatch):
    # Mês 13 não existe: strptime tem que falhar, não devolver NULL.
    data_errada = PEDIDO[:3] + ("2017-13-05 10:00:00",) + PEDIDO[4:]
    banco = preparar(tmp_path, monkeypatch, {"olist_orders_dataset": [data_errada]})
    assert transformacao.main() == 1
    assert tabelas_refined(banco) == []


def test_mesma_chave_com_conteudo_diferente_encerra_e_nao_grava_nada(
    tmp_path, monkeypatch
):
    banco = preparar(tmp_path, monkeypatch, {"olist_orders_dataset": [PEDIDO]})
    assert transformacao.main() == 0
    # Mesmo pedido_id, outro status: o programa não escolhe uma versão.
    cancelado = PEDIDO[:2] + ("canceled",) + PEDIDO[3:]
    with duckdb.connect(str(banco)) as con:
        con.execute(
            "INSERT INTO raw.olist_orders_dataset VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            list(cancelado),
        )
    assert transformacao.main() == 1
    # A refined da execução anterior fica intacta.
    assert consultar(banco, "SELECT pedido_id, status FROM refined.pedidos") == [
        ("p1", "delivered")
    ]


def test_select_que_perde_linha_da_nao_sucesso_e_nao_grava_nada(tmp_path, monkeypatch):
    p2 = ("p2",) + PEDIDO[1:]  # outro pedido: é a linha que o SELECT vai perder
    banco = preparar(tmp_path, monkeypatch, {"olist_orders_dataset": [PEDIDO, p2]})
    assert transformacao.main() == 0

    # Pedido novo na raw: se a execução com erro gravasse, ele apareceria na refined.
    p3 = ("p3",) + PEDIDO[1:]
    with duckdb.connect(str(banco)) as con:
        con.execute(
            "INSERT INTO raw.olist_orders_dataset VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            list(p3),
        )
    # Um SELECT de pedidos com defeito: perde o p2 sem avisar.
    pedidos = transformacao.TABELAS["pedidos"]
    com_defeito = dict(pedidos, select=pedidos["select"] + " WHERE order_id <> 'p2'")
    monkeypatch.setattr(
        transformacao, "TABELAS", dict(transformacao.TABELAS, pedidos=com_defeito)
    )

    assert transformacao.main() == 1
    # A refined da execução anterior fica intacta: p1 e p2, sem o p3.
    assert consultar(
        banco, "SELECT pedido_id FROM refined.pedidos ORDER BY pedido_id"
    ) == [("p1",), ("p2",)]


def test_tabela_faltando_em_raw_encerra_sem_gravar(tmp_path, monkeypatch):
    banco = preparar(tmp_path, monkeypatch, {}, sem="olist_sellers_dataset")
    assert transformacao.main() == 1
    assert tabelas_refined(banco) == []


def test_sem_banco_encerra_com_erro(tmp_path, monkeypatch):
    monkeypatch.setattr(transformacao, "BANCO", tmp_path / "olist.duckdb")
    assert transformacao.main() == 1
    assert not (tmp_path / "olist.duckdb").exists()
