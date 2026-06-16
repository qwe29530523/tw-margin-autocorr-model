from __future__ import annotations

import pandas as pd


RAW_SHELTER_COLUMNS = [
    "shelter_cpi",
    "shelter_cpi_sa",
    "rent_cpi",
    "owners_equivalent_rent",
    "mortgage_rate_30y",
    "mortgage_rate_15y",
    "case_shiller_home_price",
    "fhfa_home_price",
    "housing_starts",
    "building_permits",
    "new_home_sales",
]

SHELTER_INFLATION_OUTPUT_COLUMNS = [
    "date",
    *RAW_SHELTER_COLUMNS,
    "shelter_cpi_1m_chg",
    "shelter_cpi_3m_chg",
    "rent_cpi_1m_chg",
    "rent_cpi_3m_chg",
    "oer_1m_chg",
    "oer_3m_chg",
    "home_price_3m_roc",
    "mortgage_rate_3m_chg",
    "housing_starts_3m_roc",
    "building_permits_3m_roc",
    "shelter_cpi_trend",
    "rent_pressure",
    "oer_pressure",
    "home_price_momentum",
    "mortgage_rate_pressure",
    "housing_activity_pressure",
    "affordability_stress",
    "shelter_pipeline_pressure",
    "source_confidence",
    "missing_data_ratio",
    "source_mode",
]


def build_shelter_inflation_engine(input_df: pd.DataFrame, source_mode: str = "official") -> pd.DataFrame:
    if input_df.empty:
        return pd.DataFrame(columns=SHELTER_INFLATION_OUTPUT_COLUMNS)

    out = input_df.copy()
    if "date" not in out.columns:
        out["date"] = pd.NaT
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.sort_values("date").reset_index(drop=True)

    for column in RAW_SHELTER_COLUMNS:
        if column not in out.columns:
            out[column] = pd.NA
        out[column] = pd.to_numeric(out[column], errors="coerce")

    out["shelter_cpi_1m_chg"] = _pct_change(out["shelter_cpi"], 1)
    out["shelter_cpi_3m_chg"] = _pct_change(out["shelter_cpi"], 3)
    out["rent_cpi_1m_chg"] = _pct_change(out["rent_cpi"], 1)
    out["rent_cpi_3m_chg"] = _pct_change(out["rent_cpi"], 3)
    out["oer_1m_chg"] = _pct_change(out["owners_equivalent_rent"], 1)
    out["oer_3m_chg"] = _pct_change(out["owners_equivalent_rent"], 3)

    case_shiller_3m = _pct_change(out["case_shiller_home_price"], 3)
    fhfa_3m = _pct_change(out["fhfa_home_price"], 3)
    mortgage_30y_3m = out["mortgage_rate_30y"].diff(3)
    mortgage_15y_3m = out["mortgage_rate_15y"].diff(3)

    out["home_price_3m_roc"] = pd.concat([case_shiller_3m, fhfa_3m], axis=1).mean(axis=1, skipna=True)
    out["mortgage_rate_3m_chg"] = pd.concat([mortgage_30y_3m, mortgage_15y_3m], axis=1).mean(
        axis=1,
        skipna=True,
    )
    out["housing_starts_3m_roc"] = _pct_change(out["housing_starts"], 3)
    out["building_permits_3m_roc"] = _pct_change(out["building_permits"], 3)

    out["shelter_cpi_trend"] = _row_mean(out, ["shelter_cpi_1m_chg", "shelter_cpi_3m_chg"])
    out["rent_pressure"] = _row_mean(out, ["rent_cpi_1m_chg", "rent_cpi_3m_chg"])
    out["oer_pressure"] = _row_mean(out, ["oer_1m_chg", "oer_3m_chg"])
    out["home_price_momentum"] = out["home_price_3m_roc"]
    out["mortgage_rate_pressure"] = out["mortgage_rate_3m_chg"]
    out["housing_activity_pressure"] = _row_mean(out, ["housing_starts_3m_roc", "building_permits_3m_roc"])
    out["affordability_stress"] = _row_mean(out, ["mortgage_rate_pressure", "home_price_momentum"])
    out["shelter_pipeline_pressure"] = _row_mean(
        out,
        [
            "home_price_momentum",
            "mortgage_rate_pressure",
            "housing_activity_pressure",
            "rent_pressure",
            "oer_pressure",
        ],
    )
    out["missing_data_ratio"] = out[RAW_SHELTER_COLUMNS].isna().mean(axis=1)
    out["source_confidence"] = 1 - out["missing_data_ratio"]
    out["source_mode"] = source_mode

    return out[SHELTER_INFLATION_OUTPUT_COLUMNS]


def _pct_change(series: pd.Series, periods: int) -> pd.Series:
    return series.pct_change(periods=periods, fill_method=None)


def _row_mean(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    return frame[columns].mean(axis=1, skipna=True)
