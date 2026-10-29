"""Testes de pipeline/ingestao.py (specs/spec_ingestao.md), com CSVs inventados em tmp_path."""

import gzip

import duckdb

from pipeline import ingestao

CLIENTES = (
    "customer_id,customer_zip_code_prefix,customer_city\n"
    "c1,01151,São Paulo\n"  # CEP com zero à esquerda; acento
    "c2,22000,\n"  # cidade vazia: vira NULL
    "c3,30000,NA\n"  # o texto "NA" não é vazio
    "c3,30000,NA\n"  # linha repetida: a ingestão não apaga nada
)
OUTRAS = "coluna\nvalor\n"  # uma linha basta para as outras oito planilhas

ESPERADAS = {nome: 1 for nome in ingestao.LINHAS_ESPERADAS}
ESPERADAS["olist_customers_dataset"] = 4


def escrever_planilhas(pasta, faltando=None):
    pasta.mkdir()
    for nome in ingestao.LINHAS_ESPERADAS:
        if nome == faltando:
            continue
        texto = CLIENTES if nome == "olist_customers_dataset" else OUTRAS
        with gzip.open(pasta / f"{nome}.csv.gz", "wt", encoding="utf-8") as arquivo:
            arquivo.write(texto)


def preparar(tmp_path, monkeypatch, esperadas=ESPERADAS, faltando=None):
    escrever_planilhas(tmp_path / "raw", faltando)
    monkeypatch.setattr(ingestao, "PASTA_RAW", tmp_path / "raw")
    monkeypatch.setattr(ingestao, "BANCO", tmp_path / "olist.duckdb")
    monkeypatch.setattr(ingestao, "LINHAS_ESPERADAS", esperadas)


def clientes(tmp_path):
    with duckdb.connect(str(tmp_path / "olist.duckdb"), read_only=True) as con:
        return con.execute(
            "SELECT * FROM raw.olist_customers_dataset ORDER BY customer_id"
        ).fetchall()


def test_csv_vira_tabela_com_as_mesmas_linhas(tmp_path, monkeypatch):
    preparar(tmp_path, monkeypatch)
    assert ingestao.main() == 0
    assert len(clientes(tmp_path)) == 4


def test_todas_as_colunas_entram_como_varchar(tmp_path, monkeypatch):
    preparar(tmp_path, monkeypatch)
    ingestao.main()
    with duckdb.connect(str(tmp_path / "olist.duckdb"), read_only=True) as con:
        tipos = {
            linha[0]
            for linha in con.execute(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_schema = 'raw'"
            ).fetchall()
        }
    assert tipos == {"VARCHAR"}


def test_cep_com_zero_a_esquerda_continua_com_o_zero(tmp_path, monkeypatch):
    preparar(tmp_path, monkeypatch)
    ingestao.main()
    assert clientes(tmp_path)[0][1] == "01151"


def test_acento_chega_inteiro(tmp_path, monkeypatch):
    preparar(tmp_path, monkeypatch)
    ingestao.main()
    assert clientes(tmp_path)[0][2] == "São Paulo"


def test_campo_vazio_vira_null(tmp_path, monkeypatch):
    preparar(tmp_path, monkeypatch)
    ingestao.main()
    assert clientes(tmp_path)[1][2] is None


def test_texto_na_continua_texto(tmp_path, monkeypatch):
    preparar(tmp_path, monkeypatch)
    ingestao.main()
    assert clientes(tmp_path)[2][2] == "NA"


def test_rodar_duas_vezes_nao_duplica(tmp_path, monkeypatch):
    preparar(tmp_path, monkeypatch)
    assert ingestao.main() == 0
    assert ingestao.main() == 0
    assert len(clientes(tmp_path)) == 4


def test_arquivo_faltando_encerra_sem_gravar_nenhuma_tabela(tmp_path, monkeypatch):
    preparar(tmp_path, monkeypatch, faltando="olist_sellers_dataset")
    assert ingestao.main() == 1
    assert not (tmp_path / "olist.duckdb").exists()


def test_contagem_diferente_da_esperada_da_nao_sucesso(tmp_path, monkeypatch):
    esperadas = dict(ESPERADAS, olist_customers_dataset=5)  # o CSV tem 4
    preparar(tmp_path, monkeypatch, esperadas=esperadas)
    assert ingestao.main() == 1
