"""Abre o olist.duckdb no navegador com a extensão "ui" do DuckDB."""

import sys
import time
from pathlib import Path

import duckdb

BANCO = Path(__file__).resolve().parent / "olist.duckdb"
ENDERECO = "http://localhost:4213"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")

    if not BANCO.is_file():
        print(f"O banco {BANCO.name} não existe. Rode a ingestão antes:")
        print("    uv run python -m pipeline.ingestao")
        return 1

    con = duckdb.connect(str(BANCO))
    try:
        con.execute("INSTALL ui; LOAD ui")
        # start_ui_server() em vez de start_ui(): no WSL não há navegador para abrir.
        con.execute("CALL start_ui_server()")
        print(f"Abra no navegador: {ENDERECO}")
        print("Ctrl+C para encerrar")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print()
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
