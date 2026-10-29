"""Transformação do schema "raw" para o schema "refined" do DuckDB (specs/transformacao.md)."""

import sys
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "olist.duckdb"
ORIGEM = "raw"
DESTINO = "refined"

# Cada SELECT: remove linhas idênticas ainda como texto (DISTINCT), depois renomeia e converte.
# Conversão estrita: strptime e CAST param o programa se um valor não converter.
TABELAS = {
    "pedidos": {
        "origem": "olist_orders_dataset",
        "chave": ["pedido_id"],
        "select": """
            SELECT
              order_id AS pedido_id,
              customer_id AS cliente_id,
              order_status AS status,
              strptime(order_purchase_timestamp, '%Y-%m-%d %H:%M:%S') AS data_compra,
              strptime(order_approved_at, '%Y-%m-%d %H:%M:%S') AS data_aprovacao,
              strptime(order_delivered_carrier_date, '%Y-%m-%d %H:%M:%S') AS data_envio,
              strptime(order_delivered_customer_date, '%Y-%m-%d %H:%M:%S') AS data_entrega,
              CAST(strptime(order_estimated_delivery_date, '%Y-%m-%d %H:%M:%S') AS DATE) AS data_entrega_prevista
            FROM (SELECT DISTINCT * FROM raw.olist_orders_dataset)
        """,
    },
    "itens_pedido": {
        "origem": "olist_order_items_dataset",
        "chave": ["pedido_id", "item_seq"],
        "select": """
            SELECT
              order_id AS pedido_id,
              CAST(order_item_id AS INTEGER) AS item_seq,
              product_id AS produto_id,
              seller_id AS vendedor_id,
              strptime(shipping_limit_date, '%Y-%m-%d %H:%M:%S') AS data_limite_envio,
              CAST(price AS DECIMAL(10,2)) AS preco,
              CAST(freight_value AS DECIMAL(10,2)) AS frete
            FROM (SELECT DISTINCT * FROM raw.olist_order_items_dataset)
        """,
    },
    "pagamentos": {
        "origem": "olist_order_payments_dataset",
        "chave": ["pedido_id", "pagamento_seq"],
        "select": """
            SELECT
              order_id AS pedido_id,
              CAST(payment_sequential AS INTEGER) AS pagamento_seq,
              payment_type AS tipo,
              CAST(payment_installments AS INTEGER) AS parcelas,
              CAST(payment_value AS DECIMAL(10,2)) AS valor
            FROM (SELECT DISTINCT * FROM raw.olist_order_payments_dataset)
        """,
    },
    "avaliacoes": {
        "origem": "olist_order_reviews_dataset",
        "chave": ["avaliacao_id", "pedido_id"],
        "select": """
            SELECT
              review_id AS avaliacao_id,
              order_id AS pedido_id,
              CAST(review_score AS INTEGER) AS nota,
              review_comment_title AS titulo,
              review_comment_message AS comentario,
              CAST(strptime(review_creation_date, '%Y-%m-%d %H:%M:%S') AS DATE) AS data_criacao,
              strptime(review_answer_timestamp, '%Y-%m-%d %H:%M:%S') AS data_resposta
            FROM (SELECT DISTINCT * FROM raw.olist_order_reviews_dataset)
        """,
    },
    "clientes": {
        "origem": "olist_customers_dataset",
        "chave": ["cliente_id"],
        "select": """
            SELECT
              customer_id AS cliente_id,
              customer_unique_id AS cliente_unico_id,
              customer_zip_code_prefix AS cep_prefixo,
              customer_city AS cidade,
              customer_state AS uf
            FROM (SELECT DISTINCT * FROM raw.olist_customers_dataset)
        """,
    },
    "vendedores": {
        "origem": "olist_sellers_dataset",
        "chave": ["vendedor_id"],
        "select": """
            SELECT
              seller_id AS vendedor_id,
              seller_zip_code_prefix AS cep_prefixo,
              seller_city AS cidade,
              seller_state AS uf
            FROM (SELECT DISTINCT * FROM raw.olist_sellers_dataset)
        """,
    },
    "produtos": {
        "origem": "olist_products_dataset",
        "chave": ["produto_id"],
        "select": """
            SELECT
              product_id AS produto_id,
              product_category_name AS categoria,
              CAST(product_name_lenght AS INTEGER) AS tamanho_nome,
              CAST(product_description_lenght AS INTEGER) AS tamanho_descricao,
              CAST(product_photos_qty AS INTEGER) AS qtd_fotos,
              CAST(product_weight_g AS INTEGER) AS peso_g,
              CAST(product_length_cm AS INTEGER) AS comprimento_cm,
              CAST(product_height_cm AS INTEGER) AS altura_cm,
              CAST(product_width_cm AS INTEGER) AS largura_cm
            FROM (SELECT DISTINCT * FROM raw.olist_products_dataset)
        """,
    },
    "traducao_categorias": {
        "origem": "product_category_name_translation",
        "chave": ["categoria"],
        "select": """
            SELECT
              product_category_name AS categoria,
              product_category_name_english AS categoria_en
            FROM (SELECT DISTINCT * FROM raw.product_category_name_translation)
        """,
    },
}

MAX_LINHAS_CONFLITO = 20


class FalhaConversao(Exception):
    def __init__(self, tabela: str):
        self.tabela = tabela


class ConflitoChave(Exception):
    pass


def tabelas_faltando(con: duckdb.DuckDBPyConnection) -> list[str]:
    existentes = {
        linha[0]
        for linha in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = ?",
            [ORIGEM],
        ).fetchall()
    }
    return [t["origem"] for t in TABELAS.values() if t["origem"] not in existentes]


def contar_vazios(
    con: duckdb.DuckDBPyConnection, consulta: str
) -> tuple[list[str], list[int]]:
    # Uma linha com a quantidade de NULL de cada coluna, na ordem das colunas.
    cursor = con.execute(f"SELECT count(*) - count(COLUMNS(*)) FROM ({consulta})")
    return [d[0] for d in cursor.description], list(cursor.fetchone())


def criar_tabela(con: duckdb.DuckDBPyConnection, nome: str, select: str) -> None:
    con.execute(f"DROP TABLE IF EXISTS {DESTINO}.{nome}")
    try:
        con.execute(f"CREATE TABLE {DESTINO}.{nome} AS {select}")
    except (duckdb.ConversionException, duckdb.InvalidInputException) as erro:
        raise FalhaConversao(nome) from erro


def conferir_chave(con: duckdb.DuckDBPyConnection, nome: str, chave: list[str]) -> None:
    # Roda depois do DISTINCT: se a chave ainda repete, é a mesma chave com conteúdo diferente.
    colunas_chave = ", ".join(chave)
    repetidas = con.execute(
        f"SELECT count(*) FROM (SELECT {colunas_chave} FROM {DESTINO}.{nome} "
        f"GROUP BY ALL HAVING count(*) > 1)"
    ).fetchone()[0]
    if repetidas == 0:
        return

    cursor = con.execute(
        f"SELECT * FROM {DESTINO}.{nome} "
        f"QUALIFY count(*) OVER (PARTITION BY {colunas_chave}) > 1 "
        f"ORDER BY {colunas_chave} LIMIT {MAX_LINHAS_CONFLITO}"
    )
    colunas = [d[0] for d in cursor.description]
    linhas = cursor.fetchall()
    texto = [
        f"{nome}: {repetidas} chave(s) ({colunas_chave}) com conteúdo diferente.",
        f"Primeiras {len(linhas)} linhas em conflito:",
        "  " + " | ".join(colunas),
    ]
    texto += ["  " + " | ".join(str(v) for v in linha) for linha in linhas]
    raise ConflitoChave("\n".join(texto))


def diagnosticar_conversao(
    con: duckdb.DuckDBPyConnection, nome: str, erro: Exception
) -> None:
    # Consulta uma coluna por vez para descobrir qual não converteu; a mensagem traz o valor.
    select = TABELAS[nome]["select"]
    colunas = [linha[0] for linha in con.execute(f"DESCRIBE {select}").fetchall()]
    for coluna in colunas:
        try:
            con.execute(f"SELECT count({coluna}) FROM ({select})").fetchone()
        except duckdb.Error as erro_coluna:
            print(f"  tabela: {nome}")
            print(f"  coluna: {coluna}")
            print(f"  erro:   {str(erro_coluna).splitlines()[0]}")
            return
    print(f"  tabela: {nome}")
    print(f"  erro:   {str(erro).splitlines()[0]}")


def conferir(con: duckdb.DuckDBPyConnection) -> dict[str, list[str]]:
    diferencas = {}
    for nome, tabela in TABELAS.items():
        origem = f"{ORIGEM}.{tabela['origem']}"
        problemas = []

        entram = con.execute(f"SELECT count(*) FROM {origem}").fetchone()[0]
        distintas = con.execute(
            f"SELECT count(*) FROM (SELECT DISTINCT * FROM {origem})"
        ).fetchone()[0]
        saem = con.execute(f"SELECT count(*) FROM {DESTINO}.{nome}").fetchone()[0]
        duplicatas = entram - distintas
        if saem != entram - duplicatas:
            problemas.append(
                f"linhas: entram {entram}, duplicatas {duplicatas}, saem {saem}"
            )

        # Vazios comparados coluna a coluna, na mesma posição (o SELECT mantém a ordem da raw).
        colunas_antes, vazios_antes = contar_vazios(
            con, f"SELECT DISTINCT * FROM {origem}"
        )
        colunas_depois, vazios_depois = contar_vazios(
            con, f"SELECT * FROM {DESTINO}.{nome}"
        )
        if len(colunas_antes) != len(colunas_depois):
            problemas.append(
                f"colunas: {len(colunas_antes)} antes, {len(colunas_depois)} depois"
            )
        else:
            for coluna, antes, depois in zip(
                colunas_depois, vazios_antes, vazios_depois
            ):
                if antes != depois:
                    problemas.append(
                        f"vazios em {coluna}: {antes} antes, {depois} depois"
                    )

        print(
            f"{DESTINO}.{nome}: {saem} linhas ({duplicatas} duplicatas idênticas removidas)"
        )
        if problemas:
            diferencas[nome] = problemas
    return diferencas


def main() -> int:
    if not BANCO.is_file():
        faltando = [t["origem"] for t in TABELAS.values()]
    else:
        with duckdb.connect(str(BANCO), read_only=True) as con:
            faltando = tabelas_faltando(con)
    if faltando:
        print(f"ERRO: tabelas faltando em {ORIGEM}, nada foi gravado:")
        for nome in faltando:
            print(f"  - {ORIGEM}.{nome}")
        print("Rode antes: uv run python -m pipeline.ingestao")
        return 1

    con = duckdb.connect(str(BANCO))
    try:
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(f"CREATE SCHEMA IF NOT EXISTS {DESTINO}")
            for nome, tabela in TABELAS.items():
                criar_tabela(con, nome, tabela["select"])
                conferir_chave(con, nome, tabela["chave"])
            # Confere antes de confirmar: com NÃO SUCESSO, a refined anterior fica intacta.
            diferencas = conferir(con)
            if diferencas:
                con.execute("ROLLBACK")
            else:
                con.execute("COMMIT")
        except FalhaConversao as falha:
            con.execute("ROLLBACK")
            print("ERRO: conversão de tipo falhou, nada foi gravado:")
            diagnosticar_conversao(con, falha.tabela, falha.__cause__)
            return 1
        except ConflitoChave as conflito:
            con.execute("ROLLBACK")
            print("ERRO: mesma chave com conteúdo diferente, nada foi gravado:")
            print(conflito)
            return 1
        except Exception:
            con.execute("ROLLBACK")
            raise
    finally:
        con.close()

    if diferencas:
        print("NÃO SUCESSO (nada foi gravado)")
        for nome, problemas in diferencas.items():
            for problema in problemas:
                print(f"  {nome}: {problema}")
        return 1

    print("SUCESSO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
