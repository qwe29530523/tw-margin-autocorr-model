from __future__ import annotations

import pandas as pd

from src.systems.shelter_inflation.processors.shelter_inflation_engine import (
    SHELTER_INFLATION_OUTPUT_COLUMNS,
    build_shelter_inflation_engine,
)


FORBIDDEN_SCORE_COLUMNS = {
    "production_score",
    "inflation_pressure_score",
    "shelter_inflation_pressure_score",
    "composite_score",
}


def _monthly_fixture() -> pd.DataFrame:
    dates = pd.date_range("2025-01-31", periods=7, freq="ME")
    return pd.DataFrame(
        {
            "date": dates,
            "shelter_cpi": [100.0, 100.3, 100.7, 101.1, 101.6, 102.2, 102.9],
            "shelter_cpi_sa": [100.0, 100.2, 100.6, 101.0, 101.4, 101.9, 102.4],
            "rent_cpi": [100.0, 100.4, 100.8, 101.3, 101.8, 102.4, 103.1],
            "owners_equivalent_rent": [100.0, 100.2, 100.5, 100.9, 101.3, 101.8, 102.2],
            "mortgage_rate_30y": [6.10, 6.15, 6.20, 6.35, 6.45, 6.55, 6.70],
            "mortgage_rate_15y": [5.45, 5.50, 5.56, 5.66, 5.78, 5.88, 6.02],
            "case_shiller_home_price": [300.0, 301.0, 302.5, 305.0, 307.0, 309.5, 312.5],
            "fhfa_home_price": [410.0, 411.5, 413.0, 416.0, 419.0, 422.0, 426.0],
            "housing_starts": [1350.0, 1340.0, 1360.0, 1385.0, 1400.0, 1425.0, 1450.0],
            "building_permits": [1420.0, 1415.0, 1435.0, 1460.0, 1485.0, 1505.0, 1535.0],
            "new_home_sales": [650.0, 655.0, 660.0, 670.0, 682.0, 690.0, 705.0],
        }
    )


def test_empty_input_returns_empty_full_schema() -> None:
    result = build_shelter_inflation_engine(pd.DataFrame())

    assert result.empty
    assert list(result.columns) == SHELTER_INFLATION_OUTPUT_COLUMNS
    assert FORBIDDEN_SCORE_COLUMNS.isdisjoint(result.columns)


def test_missing_columns_do_not_crash_and_are_created_as_nan() -> None:
    input_df = pd.DataFrame(
        {
            "date": pd.date_range("2025-01-31", periods=4, freq="ME"),
            "shelter_cpi": [100.0, 100.2, 100.5, 100.8],
        }
    )

    result = build_shelter_inflation_engine(input_df, source_mode="official")

    assert list(result.columns) == SHELTER_INFLATION_OUTPUT_COLUMNS
    assert result["rent_cpi"].isna().all()
    assert result["owners_equivalent_rent"].isna().all()
    assert result["source_mode"].eq("official").all()
    assert result["missing_data_ratio"].between(0, 1).all()
    assert FORBIDDEN_SCORE_COLUMNS.isdisjoint(result.columns)


def test_monthly_fixture_produces_shelter_signals_after_enough_history() -> None:
    result = build_shelter_inflation_engine(_monthly_fixture(), source_mode="official")
    latest = result.iloc[-1]

    assert pd.notna(latest["shelter_cpi_trend"])
    assert pd.notna(latest["rent_pressure"])
    assert pd.notna(latest["oer_pressure"])
    assert pd.notna(latest["home_price_momentum"])
    assert pd.notna(latest["mortgage_rate_pressure"])
    assert pd.notna(latest["housing_activity_pressure"])
    assert pd.notna(latest["affordability_stress"])
    assert pd.notna(latest["shelter_pipeline_pressure"])
    assert latest["shelter_cpi_trend"] > 0
    assert latest["rent_pressure"] > 0
    assert latest["oer_pressure"] > 0
    assert latest["home_price_momentum"] > 0
    assert latest["mortgage_rate_pressure"] > 0
    assert latest["housing_activity_pressure"] > 0
    assert latest["shelter_pipeline_pressure"] > 0


def test_missing_data_ratio_and_source_confidence_are_row_level() -> None:
    frame = _monthly_fixture()
    frame.loc[frame.index[-1], ["rent_cpi", "case_shiller_home_price", "housing_starts"]] = pd.NA

    result = build_shelter_inflation_engine(frame, source_mode="official")
    latest = result.iloc[-1]

    assert 0 < latest["missing_data_ratio"] < 1
    assert latest["source_confidence"] == 1 - latest["missing_data_ratio"]


def test_no_production_or_composite_score_columns_exist() -> None:
    result = build_shelter_inflation_engine(_monthly_fixture())

    assert FORBIDDEN_SCORE_COLUMNS.isdisjoint(result.columns)
