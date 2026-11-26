import re
import duckdb
import pandas as pd

from config import DB_PATH

REGIAO_COMERCIALIZACAO_MAP = {
    1: "Região 1 - Nacional ou >=3 estados (SP, RJ, MG, RS, PR, BA)",
    2: "Região 2 - SP ou >1 estado (exceto critérios da Região 1)",
    3: "Região 3 - Único estado (exceto SP)",
    4: "Região 4 - Municípios SP, RJ, BH, POA, Curitiba ou Brasília",
    5: "Região 5 - Grupo de municípios (exceto Região 4)",
    6: "Região 6 - Único município (exceto Região 4)",
}


def pad_digits(series: pd.Series, width: int) -> pd.Series:
    def _clean(val):
        if pd.isna(val):
            return None
        txt = str(val).strip()
        if not txt or txt.upper() in {"NA", "N/A", "NULL", "NONE", "NAN"}:
            return None
        txt = re.sub(r"\.0$", "", txt)
        digits = re.sub(r"\D+", "", txt)
        if not digits:
            return None
        return digits.zfill(width)

    return series.map(_clean)


def clean_digits_text(series: pd.Series, min_len: int = 1, max_len: int | None = None) -> pd.Series:
    def _clean(val):
        if pd.isna(val):
            return None
        txt = str(val).strip()
        if not txt or txt.upper() in {"NA", "N/A", "NULL", "NONE", "NAN"}:
            return None
        txt = re.sub(r"\.0$", "", txt)
        digits = re.sub(r"\D+", "", txt)
        if len(digits) < min_len:
            return None
        if max_len is not None and len(digits) > max_len:
            digits = digits[:max_len]
        return digits

    return series.map(_clean)


def clean_lower_text(series: pd.Series) -> pd.Series:
    def _clean(val):
        if pd.isna(val):
            return None
        txt = re.sub(r"\s+", " ", str(val).strip()).lower()
        if not txt or txt in {"na", "n/a", "null", "none", "nan"}:
            return None
        return txt

    return series.map(_clean)


def parse_date_safe(series: pd.Series) -> pd.Series:
    def _parse(val):
        if pd.isna(val):
            return None
        txt = str(val).strip()
        if not txt or txt.upper() in {"NA", "N/A", "NULL", "NONE", "NAN", "-", "0", "00/00/0000"}:
            return None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            dt = pd.to_datetime(txt, format=fmt, errors="coerce")
            if pd.notna(dt):
                return dt.date()
        dt = pd.to_datetime(txt, errors="coerce")
        return dt.date() if pd.notna(dt) else None

    return series.map(_parse)


def parse_decimal_br(series: pd.Series) -> pd.Series:
    def _parse(val):
        if pd.isna(val):
            return None
        txt = str(val).strip().replace("%", "").replace(" ", "")
        if not txt or txt.upper() in {"NA", "N/A", "NULL", "NONE", "NAN", "-"}:
            return None
        if "," in txt and "." in txt:
            txt = txt.replace(".", "").replace(",", ".")
        elif "," in txt:
            txt = txt.replace(",", ".")
        try:
            return float(txt)
        except ValueError:
            return None

    return series.map(_parse)


def parse_int_safe(series: pd.Series) -> pd.Series:
    def _parse(val):
        if pd.isna(val):
            return None
        txt = str(val).strip()
        if not txt or txt.upper() in {"NA", "N/A", "NULL", "NONE", "NAN", "-"}:
            return None
        txt = re.sub(r"\.0$", "", txt)
        digits = re.sub(r"[^\d-]", "", txt)
        if not digits or digits == "-":
            return None
        try:
            return int(digits)
        except ValueError:
            return None

    return series.map(_parse)


def run_silver() -> None:
    conn = duckdb.connect(str(DB_PATH))
    try:
        conn.execute("CREATE SCHEMA IF NOT EXISTS silver;")

        # 1. Dimensão de operadoras (ativas + canceladas + enriquecimento acreditadas)
        ativas = conn.sql("SELECT * FROM bronze.operadoras_ativas").df()
        canceladas = conn.sql("SELECT * FROM bronze.operadoras_canceladas").df()

        ativas["_status_registro"] = "ATIVO"
        canceladas["_status_registro"] = "CANCELADO"

        ops = pd.concat([ativas, canceladas], ignore_index=True)

        if "REGISTRO_OPERADORA" in ops.columns:
            ops["registro_ans"] = pad_digits(ops["REGISTRO_OPERADORA"], 6)
        if "CNPJ" in ops.columns:
            ops["cnpj_padronizado"] = pad_digits(ops["CNPJ"], 14)
        if "CEP" in ops.columns:
            ops["CEP"] = clean_digits_text(ops["CEP"], min_len=5, max_len=8)
        if "DDD" in ops.columns:
            ops["DDD"] = clean_digits_text(ops["DDD"], min_len=2, max_len=2)
        if "TELEFONE" in ops.columns:
            ops["TELEFONE"] = clean_digits_text(ops["TELEFONE"], min_len=7, max_len=11)
        if "FAX" in ops.columns:
            ops["FAX"] = clean_digits_text(ops["FAX"], min_len=7, max_len=11)
        if "ENDERECO_ELETRONICO" in ops.columns:
            ops["ENDERECO_ELETRONICO"] = clean_lower_text(ops["ENDERECO_ELETRONICO"])
        if "CARGO_REPRESENTANTE" in ops.columns:
            ops["CARGO_REPRESENTANTE"] = clean_lower_text(ops["CARGO_REPRESENTANTE"])

        col_regiao = next(
            (c for c in ops.columns if "regiao" in c.lower() and "comercial" in c.lower()),
            None,
        )
        if col_regiao:
            regiao_int = parse_int_safe(ops[col_regiao])
            ops[col_regiao] = regiao_int
            ops["regiao_comercializacao_desc"] = regiao_int.map(REGIAO_COMERCIALIZACAO_MAP)

        date_cols_ops = [c for c in ops.columns if "data" in c.lower() or c.startswith("DT_")]
        for col in date_cols_ops:
            ops[col] = parse_date_safe(ops[col])

        # Acreditadas 2025 via LEFT JOIN deduplicado por registro_ans
        acreditadas = conn.sql("SELECT * FROM bronze.acreditadas_2025").df()
        col_reg_acred = next(
            (c for c in acreditadas.columns if "reg" in c.lower() and "ans" in c.lower()),
            None,
        )
        if col_reg_acred and "registro_ans" in ops.columns:
            acred = acreditadas.copy()
            acred["registro_ans"] = pad_digits(acred[col_reg_acred], 6)
            for c in acreditadas.columns:
                if "validade" in c.lower() or "data" in c.lower() or c.startswith("DT_"):
                    acred[c] = parse_date_safe(acred[c])

            # Mantém 1 linha por operadora (priorizando maior prazo/fim de validade se houver repetição)
            sort_col = next(
                (c for c in acred.columns if "fim" in c.lower() and "validade" in c.lower()),
                None,
            )
            if sort_col:
                acred = acred.sort_values(by=sort_col, ascending=False, na_position="last")
            acred = acred.drop_duplicates(subset=["registro_ans"], keep="first")

            cols_to_merge = [
                c for c in acred.columns
                if c not in {col_reg_acred, "_arquivo_origem", "_dt_ingestao"}
            ]
            acred_sub = acred[cols_to_merge].rename(
                columns={
                    c: f"acreditacao_{c}" if c != "registro_ans" else c
                    for c in cols_to_merge
                }
            )
            acred_sub["acreditada"] = True

            ops = ops.merge(acred_sub, on="registro_ans", how="left")
            ops["acreditada"] = ops["acreditada"].fillna(False).astype(bool)

        conn.register("df_silver_ops", ops)
        conn.execute("CREATE OR REPLACE TABLE silver.dim_operadoras AS SELECT * FROM df_silver_ops;")
        if col_regiao:
            conn.execute(
                f'ALTER TABLE silver.dim_operadoras ALTER COLUMN "{col_regiao}" TYPE INTEGER USING TRY_CAST("{col_regiao}" AS INTEGER);'
            )
        for col in date_cols_ops:
            conn.execute(
                f'ALTER TABLE silver.dim_operadoras ALTER COLUMN "{col}" TYPE DATE USING TRY_CAST("{col}" AS DATE);'
            )
        for col in ops.columns:
            if col.startswith("acreditacao_") and ("validade" in col.lower() or "data" in col.lower()):
                conn.execute(
                    f'ALTER TABLE silver.dim_operadoras ALTER COLUMN "{col}" TYPE DATE USING TRY_CAST("{col}" AS DATE);'
                )
        conn.unregister("df_silver_ops")

        # 2. Fato de resolutividade
        res = conn.sql("SELECT * FROM bronze.resolutividade").df()
        if "CD_REGISTRO_ANS" in res.columns:
            res["registro_ans"] = pad_digits(res["CD_REGISTRO_ANS"], 6)
        if "VL_TR" in res.columns:
            res["vl_tr_num"] = parse_decimal_br(res["VL_TR"])
        for num_col in ("NR_NUMERADOR", "NR_DENOMINADOR"):
            if num_col in res.columns:
                res[f"{num_col.lower()}_int"] = parse_int_safe(res[num_col])

        date_cols_res = [c for c in res.columns if "data" in c.lower() or c.startswith("DT_")]
        for col in date_cols_res:
            res[col] = parse_date_safe(res[col])

        conn.register("df_silver_res", res)
        conn.execute("CREATE OR REPLACE TABLE silver.fato_resolutividade AS SELECT * FROM df_silver_res;")
        if "vl_tr_num" in res.columns:
            conn.execute(
                'ALTER TABLE silver.fato_resolutividade ALTER COLUMN "vl_tr_num" TYPE DOUBLE USING TRY_CAST("vl_tr_num" AS DOUBLE);'
            )
        for num_col in ("NR_NUMERADOR", "NR_DENOMINADOR"):
            target_col = f"{num_col.lower()}_int"
            if target_col in res.columns:
                conn.execute(
                    f'ALTER TABLE silver.fato_resolutividade ALTER COLUMN "{target_col}" TYPE BIGINT USING TRY_CAST("{target_col}" AS BIGINT);'
                )
        for col in date_cols_res:
            conn.execute(
                f'ALTER TABLE silver.fato_resolutividade ALTER COLUMN "{col}" TYPE DATE USING TRY_CAST("{col}" AS DATE);'
            )
        conn.unregister("df_silver_res")

        # 3. Fato de IGR
        igr = conn.sql("SELECT * FROM bronze.igr").df()
        col_reg_igr = next(
            (c for c in igr.columns if "reg" in c.lower() and ("ans" in c.lower() or "operadora" in c.lower())),
            None,
        )
        if col_reg_igr:
            igr["registro_ans"] = pad_digits(igr[col_reg_igr], 6)

        date_cols_igr = [c for c in igr.columns if "data" in c.lower() or c.startswith("DT_")]
        for col in date_cols_igr:
            igr[col] = parse_date_safe(igr[col])

        for col in igr.columns:
            if col.startswith("_") or col == "registro_ans" or col in date_cols_igr:
                continue
            if any(k in col.lower() for k in ("igr", "taxa", "indice", "percent", "vl_", "vr_")):
                igr[f"{col.lower()}_num"] = parse_decimal_br(igr[col])
            elif any(k in col.lower() for k in ("qtd", "qt_", "nr_", "num", "den", "benef")):
                igr[f"{col.lower()}_int"] = parse_int_safe(igr[col])

        conn.register("df_silver_igr", igr)
        conn.execute("CREATE OR REPLACE TABLE silver.fato_igr AS SELECT * FROM df_silver_igr;")
        for col in date_cols_igr:
            conn.execute(
                f'ALTER TABLE silver.fato_igr ALTER COLUMN "{col}" TYPE DATE USING TRY_CAST("{col}" AS DATE);'
            )
        for col in igr.columns:
            if col.endswith("_num"):
                conn.execute(
                    f'ALTER TABLE silver.fato_igr ALTER COLUMN "{col}" TYPE DOUBLE USING TRY_CAST("{col}" AS DOUBLE);'
                )
            elif col.endswith("_int"):
                conn.execute(
                    f'ALTER TABLE silver.fato_igr ALTER COLUMN "{col}" TYPE BIGINT USING TRY_CAST("{col}" AS BIGINT);'
                )
        conn.unregister("df_silver_igr")

        print("[SILVER] dim_operadoras, fato_resolutividade e fato_igr atualizadas.")
    finally:
        conn.close()


if __name__ == "__main__":
    run_silver()