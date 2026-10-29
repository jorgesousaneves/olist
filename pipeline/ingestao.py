"""Ingestão das planilhas da Olist (raw/*.csv.gz) para o schema "raw" do DuckDB."""

import sys
from pathlib import Path

import duckdb
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
PASTA_RAW = RAIZ / "raw"
BANCO = RAIZ / "olist.duckdb"
SCHEMA = "raw"

LINHAS_ESPERADAS = {
    "olist_customers_dataset": 99441,
    "olist_geolocation_dataset": 1000163,
    "olist_order_items_dataset": 112650,
    "olist_order_payments_dataset": 103886,
    "olist_order_reviews_dataset": 99224,
    "olist_orders_dataset": 99441,
    "olist_products_dataset": 32951,
    "olist_sellers_dataset": 3095,
    "product_category_name_translation": 71,
}


def arquivo(tabela: str) -> Path:
    return PASTA_RAW / f"{tabela}.csv.gz"


def ler_csv(caminho: Path) -> pd.DataFrame:
    # Tudo como texto; só o campo vazio vira NULL ("NA", "N/a" etc. ficam como texto).
    # utf-8-sig remove o BOM do cabeçalho, quando existir.
    return pd.read_csv(
        caminho,
        compression="gzip",
        encoding="utf-8-sig",
        dtype=str,
        keep_default_na=False,
        na_values=[""],
    )


def main() -> int:
    faltando = [arquivo(t).name for t in LINHAS_ESPERADAS if not arquivo(t).is_file()]
    if faltando:
        print("ERRO: planilhas faltando em raw/, nada foi copiado:")
        for nome in faltando:
            print(f"  - {nome}")
        return 1

    con = duckdb.connect(str(BANCO))
    try:
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
            for tabela in LINHAS_ESPERADAS:
                df = ler_csv(arquivo(tabela))
                con.register("df_origem", df)
                con.execute(f'DROP TABLE IF EXISTS {SCHEMA}."{tabela}"')
                con.execute(f'CREATE TABLE {SCHEMA}."{tabela}" AS SELECT * FROM df_origem')
                con.unregister("df_origem")
                print(f"carregada: {SCHEMA}.{tabela}")
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise

        diferentes = {}
        for tabela, esperado in LINHAS_ESPERADAS.items():
            contado = con.execute(f'SELECT COUNT(*) FROM {SCHEMA}."{tabela}"').fetchone()[0]
            if contado != esperado:
                diferentes[tabela] = (contado, esperado)
    finally:
        con.close()

    if diferentes:
        print("NÃO SUCESSO")
        for tabela, (contado, esperado) in diferentes.items():
            print(f"  {tabela}: {contado} linhas (esperado {esperado})")
        return 1

    print("SUCESSO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
