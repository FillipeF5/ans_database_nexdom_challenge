from datetime import datetime, timezone
import re
import duckdb
import pandas as pd

from config import DB_PATH, RAW_FILES


def _fix_mojibake(value: str) -> str:
    """Tenta corrigir sequências comuns de encoding misturado sem perder texto válido."""
    if not isinstance(value, str):
        return value

    text = value.strip()
    if not text:
        return text

    # Caso clássico: string em UTF-8 decodificada indevidamente como latin1/cp1252
    if any(ch in text for ch in ("Ã", "Â", "â")):
        try:
            repaired = text.encode("cp1252").decode("utf-8")
            if repaired.count("\ufffd") <= text.count("\ufffd"):
                text = repaired
        except Exception:
            pass

    # Remove caractere de substituição solto quando sobra artefato de leitura
    text = text.replace("\ufffd", " ")
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


def _normalize_text_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        if col.startswith("_"):
            continue
        if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
            df[col] = df[col].map(
                lambda v: _fix_mojibake(v) if pd.notna(v) else v
            )
    return df


def read_ans_csv(csv_path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {csv_path}")

    encodings = ("utf-8-sig", "utf-8", "cp1252", "latin1")
    last_error = None

    for enc in encodings:
        try:
            df = pd.read_csv(
                csv_path,
                sep=";",
                encoding=enc,
                low_memory=False,
            )
            return _normalize_text_columns(df)
        except UnicodeDecodeError as err:
            last_error = err

    # Fallback final para não travar a ingestão caso haja byte isolado fora do padrão
    df = pd.read_csv(
        csv_path,
        sep=";",
        encoding="cp1252",
        encoding_errors="replace",
        low_memory=False,
    )
    if last_error is not None:
        print(f"[AVISO ENCODING] {csv_path.name}: fallback com replace aplicado ({last_error})")
    return _normalize_text_columns(df)


def run_bronze() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(DB_PATH))
    dt_ingestao = datetime.now(timezone.utc).isoformat()

    try:
        conn.execute("CREATE SCHEMA IF NOT EXISTS bronze;")
        conn.execute("CREATE SCHEMA IF NOT EXISTS silver;")
        conn.execute("CREATE SCHEMA IF NOT EXISTS gold;")

        for table_name, file_path in RAW_FILES.items():
            df = read_ans_csv(file_path)
            df["_arquivo_origem"] = file_path.name
            df["_dt_ingestao"] = dt_ingestao

            target = f"bronze.{table_name}"
            conn.register("df_bronze_stage", df)
            conn.execute(f"CREATE OR REPLACE TABLE {target} AS SELECT * FROM df_bronze_stage;")
            conn.unregister("df_bronze_stage")

            total_rows = conn.sql(f"SELECT COUNT(*) FROM {target}").fetchall()[0][0]
            print(f"[BRONZE] {target}: {total_rows:,} linhas carregadas ({file_path.name})")
    finally:
        conn.close()


if __name__ == "__main__":
    run_bronze()