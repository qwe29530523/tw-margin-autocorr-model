from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = [
    "date",
    "us_total_rigs",
    "us_oil_rigs",
    "us_gas_rigs",
    "canada_total_rigs",
    "international_total_rigs",
]

CANDIDATES = {
    "date": ["date", "week_ending", "report_date"],
    "us_total_rigs": ["us_total_rigs", "u_s_total_rigs", "us_total", "total_us"],
    "us_oil_rigs": ["us_oil_rigs", "u_s_oil_rigs", "us_oil", "oil_us"],
    "us_gas_rigs": ["us_gas_rigs", "u_s_gas_rigs", "us_gas", "gas_us"],
    "canada_total_rigs": ["canada_total_rigs", "canada_total"],
    "international_total_rigs": ["international_total_rigs", "international_total", "intl_total"],
}


def normalize_column(name: object) -> str:
    text = str(name).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def load_baker_hughes_rig_count(file_path: str | Path) -> pd.DataFrame:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Baker Hughes rig count file not found: {path}")
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    elif path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    else:
        raise ValueError("Baker Hughes file must be CSV or XLSX/XLS.")

    normalized = {column: normalize_column(column) for column in df.columns}
    df = df.rename(columns=normalized)
    reverse_lookup = {value: key for key, values in CANDIDATES.items() for value in values}
    rename_map = {column: reverse_lookup[column] for column in df.columns if column in reverse_lookup}
    df = df.rename(columns=rename_map)

    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(
            "Baker Hughes columns did not match expected schema. "
            f"Missing: {missing}. Available normalized columns: {list(df.columns)}"
        )
    out = df[REQUIRED_COLUMNS].copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for column in REQUIRED_COLUMNS:
        if column != "date":
            out[column] = pd.to_numeric(out[column], errors="coerce")
    return out.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
