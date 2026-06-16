from __future__ import annotations

import pandas as pd


RAW_FOOD_COLUMNS = [
    "food_cpi",
    "food_at_home_cpi",
    "food_ppi",
    "wheat_price",
    "corn_price",
    "soybean_price",
    "rice_price",
    "beef_price",
    "meat_ppi",
]

FOOD_INFLATION_OUTPUT_COLUMNS = [
    "date",
    *RAW_FOOD_COLUMNS,
    "food_cpi_1m_chg",
    "food_cpi_3m_chg",
    "food_ppi_1m_chg",
    "food_ppi_3m_chg",
    "wheat_3m_roc",
    "corn_3m_roc",
    "soybean_3m_roc",
    "grain_pressure",
    "meat_protein_pressure",
    "food_cpi_trend",
    "food_ppi_pipeline_pressure",
    "food_commodity_momentum",
    "source_confidence",
    "missing_data_ratio",
    "source_mode",
]


def build_food_inflation_engine(input_df: pd.DataFrame, source_mode: str = "official") -> pd.DataFrame:
    if input_df.empty:
        return pd.DataFrame(columns=FOOD_INFLATION_OUTPUT_COLUMNS)

    out = input_df.copy()
    if "date" not in out.columns:
        out["date"] = pd.NaT
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.sort_values("date").reset_index(drop=True)

    for column in RAW_FOOD_COLUMNS:
        if column not in out.columns:
            out[column] = pd.NA
        out[column] = pd.to_numeric(out[column], errors="coerce")

    out["food_cpi_1m_chg"] = _pct_change(out["food_cpi"], 1)
    out["food_cpi_3m_chg"] = _pct_change(out["food_cpi"], 3)
    out["food_ppi_1m_chg"] = _pct_change(out["food_ppi"], 1)
    out["food_ppi_3m_chg"] = _pct_change(out["food_ppi"], 3)
    out["wheat_3m_roc"] = _pct_change(out["wheat_price"], 3)
    out["corn_3m_roc"] = _pct_change(out["corn_price"], 3)
    out["soybean_3m_roc"] = _pct_change(out["soybean_price"], 3)
    beef_3m_roc = _pct_change(out["beef_price"], 3)
    meat_ppi_3m_roc = _pct_change(out["meat_ppi"], 3)
    rice_3m_roc = _pct_change(out["rice_price"], 3)

    out["grain_pressure"] = _row_mean(out, ["wheat_3m_roc", "corn_3m_roc", "soybean_3m_roc"])
    out["meat_protein_pressure"] = pd.concat([beef_3m_roc, meat_ppi_3m_roc], axis=1).mean(axis=1, skipna=True)
    out["food_cpi_trend"] = _row_mean(out, ["food_cpi_1m_chg", "food_cpi_3m_chg"])
    out["food_ppi_pipeline_pressure"] = _row_mean(out, ["food_ppi_1m_chg", "food_ppi_3m_chg"])
    out["food_commodity_momentum"] = pd.concat(
        [
            out["wheat_3m_roc"],
            out["corn_3m_roc"],
            out["soybean_3m_roc"],
            rice_3m_roc,
            beef_3m_roc,
        ],
        axis=1,
    ).mean(axis=1, skipna=True)
    out["missing_data_ratio"] = out[RAW_FOOD_COLUMNS].isna().mean(axis=1)
    out["source_confidence"] = 1 - out["missing_data_ratio"]
    out["source_mode"] = source_mode

    return out[FOOD_INFLATION_OUTPUT_COLUMNS]


def _pct_change(series: pd.Series, periods: int) -> pd.Series:
    return series.pct_change(periods=periods, fill_method=None)


def _row_mean(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    return frame[columns].mean(axis=1, skipna=True)
