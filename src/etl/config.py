from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

DATA_RAW_DIR = BASE_DIR / "data" / "raw"
DATA_GOLD_DIR = BASE_DIR / "data" / "gold"
WAREHOUSE_DIR = BASE_DIR / "warehouse"
DB_PATH = WAREHOUSE_DIR / "ans_database.duckdb"

RAW_FILES = {
    "operadoras_ativas": DATA_RAW_DIR / "operadoras_registro_ativo.csv",
    "operadoras_canceladas": DATA_RAW_DIR / "operadoras_registro_cancelado.csv",
    "igr": DATA_RAW_DIR / "IGR.csv",
    "resolutividade": DATA_RAW_DIR / "taxa_de_resolutividade.csv",
    "acreditadas_2025": DATA_RAW_DIR / "operadoras_acreditadas_2025.csv",
}