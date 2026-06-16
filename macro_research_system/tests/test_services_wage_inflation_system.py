from __future__ import annotations

import pandas as pd

from src.systems.services_wage_inflation.processors.services_wage_inflation_engine import (
    SERVICES_WAGE_INFLATION_OUTPUT_COLUMNS,
    build_services_wage_inflation_engine,
)


FORBIDDEN_SCORE_COLUMNS = {
    "production_score",
    "inflation_pressure_score",
    "services_wage_inflation_pressure_score",
    "composite_score",
}


def _monthly_fixture() -> pd.DataFrame:
    dates = pd.date_range("2025-01-31", periods=7, freq="ME")
    return pd.DataFrame(
        {
            "date": dates,
            "core_services_ex_shelter_proxy": [100.0, 100.2, 100.5, 100.9, 101.4, 102.0, 102.7],
            "average_hourly_earnings": [35.0, 35.1, 35.25, 35.45, 35.70, 36.00, 36.35],
            "employment_cost_index_wages": [160.0, 160.4, 160.9, 161.5, 162.2, 163.0, 163.9],
            "unit_labor_cost": [120.0, 120.2, 120.7, 121.3, 122.0, 122.8, 123.7],
            "compensation_per_hour": [140.0, 140.5, 141.1, 141.8, 142.6, 143.5, 144.5],
            "nonfarm_payrolls": [158000.0, 158150.0, 158320.0, 158550.0, 158820.0, 159100.0, 159420.0],
            "unemployment_rate": [4.2, 4.1, 4.0, 3.95, 3.9, 3.85, 3.8],
            "job_openings": [8000.0, 8050.0, 8120.0, 8210.0, 8320.0, 8440.0, 8570.0],
            "quits_rate": [2.0, 2.02, 2.04, 2.07, 2.10, 2.13, 2.17],
            "initial_claims": [230.0, 228.0, 225.0, 222.0, 218.0, 214.0, 210.0],
            "continuing_claims": [1820.0, 1815.0, 1805.0, 1790.0, 1770.0, 1750.0, 1730.0],
        }
    )


def test_empty_input_returns_empty_full_schema() -> None:
    result = build_services_wage_inflation_engine(pd.DataFrame())

    assert result.empty
    assert list(result.columns) == SERVICES_WAGE_INFLATION_OUTPUT_COLUMNS
    assert FORBIDDEN_SCORE_COLUMNS.isdisjoint(result.columns)


def test_missing_columns_do_not_crash_and_are_created_as_nan() -> None:
    input_df = pd.DataFrame(
        {
            "date": pd.date_range("2025-01-31", periods=4, freq="ME"),
            "core_services_ex_shelter_proxy": [100.0, 100.2, 100.5, 100.9],
        }
    )

    result = build_services_wage_inflation_engine(input_df, source_mode="official")

    assert list(result.columns) == SERVICES_WAGE_INFLATION_OUTPUT_COLUMNS
    assert result["average_hourly_earnings"].isna().all()
    assert result["employment_cost_index_wages"].isna().all()
    assert result["source_mode"].eq("official").all()
    assert result["missing_data_ratio"].between(0, 1).all()
    assert FORBIDDEN_SCORE_COLUMNS.isdisjoint(result.columns)


def test_monthly_fixture_produces_services_wage_signals_after_enough_history() -> None:
    result = build_services_wage_inflation_engine(_monthly_fixture(), source_mode="official")
    latest = result.iloc[-1]

    assert pd.notna(latest["services_cpi_trend"])
    assert pd.notna(latest["core_services_pressure"])
    assert pd.notna(latest["supercore_services_proxy"])
    assert pd.notna(latest["wage_growth_pressure"])
    assert pd.notna(latest["labor_cost_pressure"])
    assert pd.notna(latest["labor_market_tightness"])
    assert pd.notna(latest["quits_pressure"])
    assert pd.notna(latest["payroll_momentum"])
    assert pd.notna(latest["claims_stress_inverse"])
    assert pd.notna(latest["services_wage_pipeline_pressure"])
    assert latest["services_cpi_trend"] > 0
    assert latest["wage_growth_pressure"] > 0
    assert latest["labor_cost_pressure"] > 0
    assert latest["labor_market_tightness"] > 0
    assert latest["quits_pressure"] > 0
    assert latest["payroll_momentum"] > 0
    assert latest["claims_stress_inverse"] > 0
    assert latest["services_wage_pipeline_pressure"] > 0


def test_missing_data_ratio_and_source_confidence_are_row_level() -> None:
    frame = _monthly_fixture()
    frame.loc[frame.index[-1], ["average_hourly_earnings", "job_openings", "initial_claims"]] = pd.NA

    result = build_services_wage_inflation_engine(frame, source_mode="official")
    latest = result.iloc[-1]

    assert 0 < latest["missing_data_ratio"] < 1
    assert latest["source_confidence"] == 1 - latest["missing_data_ratio"]


def test_no_production_or_composite_score_columns_exist() -> None:
    result = build_services_wage_inflation_engine(_monthly_fixture())

    assert FORBIDDEN_SCORE_COLUMNS.isdisjoint(result.columns)
