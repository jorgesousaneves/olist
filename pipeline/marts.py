"""Cria o schema "marts" do DuckDB a partir dos arquivos sql/marts/*.sql (specs/marts.md)."""

import re
import sys
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "olist.duckdb"
PASTA_SQL = RAIZ / "sql" / "marts"
ORIGEM = "refined"
DESTINO = "marts"

TABELAS_ORIGEM = [
    "pedidos",
    "itens_pedido",
    "pagamentos",
    "avaliacoes",
    "clientes",
    "vendedores",
    "produtos",
    "traducao_categorias",
]

# 01_vendas_mensais.sql -> vendas_mensais
PREFIXO = re.compile(r"^\d{2}_(.+)$")


class FalhaMart(Exception):
    pass


def formatar(numero: int) -> str:
    return f"{numero:,}".replace(",", ".")


def tabelas_faltando() -> list[str]:
    if not BANCO.is_file():
        return TABELAS_ORIGEM
    with duckdb.connect(str(BANCO), read_only=True) as con:
        existentes = {
            linha[0]
            for linha in con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = ?",
                [ORIGEM],
            ).fetchall()
        }
    return [t for t in TABELAS_ORIGEM if t not in existentes]


def ler_marts() -> list[tuple[Path, str]]:
    # Valida os nomes de todos os arquivos antes de qualquer SQL rodar.
    arquivos = sorted(PASTA_SQL.glob("*.sql"))
    if not arquivos:
        raise FalhaMart(f"ERRO: nenhum arquivo .sql em {PASTA_SQL.relative_to(RAIZ)}/")

    sem_prefixo = [a.name for a in arquivos if not PREFIXO.match(a.stem)]
    if sem_prefixo:
        texto = ["ERRO: arquivos sem o prefixo NN_ (ex.: 01_vendas_mensais.sql):"]
        texto += [f"  - {nome}" for nome in sem_prefixo]
        raise FalhaMart("\n".join(texto))

    # O DuckDB não diferencia maiúsculas de minúsculas no nome da tabela.
    por_nome: dict[str, list[str]] = {}
    for arquivo in arquivos:
        nome = PREFIXO.match(arquivo.stem).group(1)
        por_nome.setdefault(nome.lower(), []).append(arquivo.name)
    repetidos = {nome: lista for nome, lista in por_nome.items() if len(lista) > 1}
    if repetidos:
        texto = ["ERRO: arquivos que dão o mesmo nome de tabela:"]
        for nome, lista in repetidos.items():
            texto.append(f"  {DESTINO}.{nome}: {', '.join(lista)}")
        raise FalhaMart("\n".join(texto))

    return [(arquivo, PREFIXO.match(arquivo.stem).group(1)) for arquivo in arquivos]


def ler_select(arquivo: Path) -> str:
    select = arquivo.read_text(encoding="utf-8").strip()
    if select.endswith(";"):
        select = select[:-1].rstrip()
    return select


def main() -> int:
    # Garante os acentos e o ✓ mesmo num terminal que não esteja em UTF-8.
    sys.stdout.reconfigure(encoding="utf-8")

    faltando = tabelas_faltando()
    if faltando:
        print(f"ERRO: tabelas faltando em {ORIGEM}, nada foi gravado:")
        for nome in faltando:
            print(f"  - {ORIGEM}.{nome}")
        print("Rode antes: uv run python -m pipeline.transformacao")
        return 1

    try:
        marts = ler_marts()
    except FalhaMart as falha:
        print(falha)
        return 1

    largura = max(len(f"{DESTINO}.{nome}") for _, nome in marts)
    total = 0
    con = duckdb.connect(str(BANCO))
    try:
        con.execute("BEGIN TRANSACTION")
        try:
            # Apaga e recria: um mart cujo arquivo sumiu não pode continuar no banco.
            con.execute(f"DROP SCHEMA IF EXISTS {DESTINO} CASCADE")
            con.execute(f"CREATE SCHEMA {DESTINO}")
            for arquivo, nome in marts:
                try:
                    con.execute(
                        f"CREATE TABLE {DESTINO}.{nome} AS {ler_select(arquivo)}"
                    )
                except duckdb.Error as erro:
                    raise FalhaMart(
                        f"ERRO: {PASTA_SQL.relative_to(RAIZ)}/{arquivo.name} falhou:\n{erro}"
                    ) from erro
                linhas = con.execute(
                    f"SELECT count(*) FROM {DESTINO}.{nome}"
                ).fetchone()[0]
                if linhas == 0:
                    raise FalhaMart(
                        f"ERRO: {DESTINO}.{nome} ({arquivo.name}) voltou com zero linhas."
                    )
                print(
                    f"✓ {f'{DESTINO}.{nome}':<{largura}}  {formatar(linhas):>9} linhas"
                )
                total += linhas
            con.execute("COMMIT")
        except FalhaMart as falha:
            con.execute("ROLLBACK")
            print(falha)
            print(f"Nada foi gravado: o schema {DESTINO} continua como estava.")
            return 1
        except Exception:
            con.execute("ROLLBACK")
            raise
    finally:
        con.close()

    print(f"{len(marts)} marts, {formatar(total)} linhas no total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
