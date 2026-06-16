from __future__ import annotations

import pandas as pd


RAW_SERVICES_WAGE_COLUMNS = [
    "core_services_ex_shelter_proxy",
    "average_hourly_earnings",
    "employment_cost_index_wages",
    "unit_labor_cost",
    "compensation_per_hour",
    "nonfarm_payrolls",
    "unemployment_rate",
    "job_openings",
    "quits_rate",
    "initial_claims",
    "continuing_claims",
]

SERVICES_WAGE_INFLATION_OUTPUT_COLUMNS = [
    "date",
    *RAW_SERVICES_WAGE_COLUMNS,
    "core_services_1m_chg",
    "core_services_3m_chg",
    "wage_ahe_3m_roc",
    "eci_3m_roc",
    "unit_labor_cost_3m_roc",
    "compensation_per_hour_3m_roc",
    "payrolls_3m_roc",
    "unemployment_rate_3m_chg",
    "job_openings_3m_roc",
    "quits_rate_3m_chg",
    "initial_claims_3m_chg",
    "continuing_claims_3m_chg",
    "services_cpi_trend",
    "core_services_pressure",
    "supercore_services_proxy",
    "wage_growth_pressure",
    "labor_cost_pressure",
    "labor_market_tightness",
    "quits_pressure",
    "payroll_momentum",
    "claims_stress_inverse",
    "services_wage_pipeline_pressure",
    "source_confidence",
    "missing_data_ratio",
    "source_mode",
]


def build_services_wage_inflation_engine(
    input_df: pd.DataFrame,
    source_mode: str = "official",
) -> pd.DataFrame:
    if input_df.empty:
        return pd.DataFrame(columns=SERVICES_WAGE_INFLATION_OUTPUT_COLUMNS)

    out = input_df.copy()
    if "date" not in out.columns:
        out["date"] = pd.NaT
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.sort_values("date").reset_index(drop=True)

    for column in RAW_SERVICES_WAGE_COLUMNS:
        if column not in out.columns:
            out[column] = pd.NA
        out[column] = pd.to_numeric(out[column], errors="coerce")

    out["core_services_1m_chg"] = _pct_change(out["core_services_ex_shelter_proxy"], 1)
    out["core_services_3m_chg"] = _pct_change(out["core_services_ex_shelter_proxy"], 3)
    out["wage_ahe_3m_roc"] = _pct_change(out["average_hourly_earnings"], 3)
    out["eci_3m_roc"] = _pct_change(out["employment_cost_index_wages"], 3)
    out["unit_labor_cost_3m_roc"] = _pct_change(out["unit_labor_cost"], 3)
    out["compensation_per_hour_3m_roc"] = _pct_change(out["compensation_per_hour"], 3)
    out["payrolls_3m_roc"] = _pct_change(out["nonfarm_payrolls"], 3)
    out["unemployment_rate_3m_chg"] = out["unemployment_rate"].diff(3)
    out["job_openings_3m_roc"] = _pct_change(out["job_openings"], 3)
    out["quits_rate_3m_chg"] = out["quits_rate"].diff(3)
    out["initial_claims_3m_chg"] = _pct_change(out["initial_claims"], 3)
    out["continuing_claims_3m_chg"] = _pct_change(out["continuing_claims"], 3)

    out["services_cpi_trend"] = _row_mean(out, ["core_services_1m_chg", "core_services_3m_chg"])
    out["core_services_pressure"] = out["services_cpi_trend"]
    out["supercore_services_proxy"] = out["core_services_pressure"]
    out["wage_growth_pressure"] = _row_mean(out, ["wage_ahe_3m_roc", "eci_3m_roc"])
    out["labor_cost_pressure"] = _row_mean(out, ["unit_labor_cost_3m_roc", "compensation_per_hour_3m_roc"])
    out["labor_market_tightness"] = pd.concat(
        [
            out["job_openings_3m_roc"],
            out["quits_rate_3m_chg"],
            -out["unemployment_rate_3m_chg"],
        ],
        axis=1,
    ).mean(axis=1, skipna=True)
    out["quits_pressure"] = out["quits_rate_3m_chg"]
    out["payroll_momentum"] = out["payrolls_3m_roc"]
    out["claims_stress_inverse"] = -_row_mean(out, ["initial_claims_3m_chg", "continuing_claims_3m_chg"])
    out["services_wage_pipeline_pressure"] = _row_mean(
        out,
        [
            "core_services_pressure",
            "wage_growth_pressure",
            "labor_cost_pressure",
            "labor_market_tightness",
            "quits_pressure",
            "payroll_momentum",
            "claims_stress_inverse",
        ],
    )
    out["missing_data_ratio"] = out[RAW_SERVICES_WAGE_COLUMNS].isna().mean(axis=1)
    out["source_confidence"] = 1 - out["missing_data_ratio"]
    out["source_mode"] = source_mode

    return out[SERVICES_WAGE_INFLATION_OUTPUT_COLUMNS]


def _pct_change(series: pd.Series, periods: int) -> pd.Series:
    return series.pct_change(periods=periods, fill_method=None)


def _row_mean(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    return frame[columns].mean(axis=1, skipna=True)
