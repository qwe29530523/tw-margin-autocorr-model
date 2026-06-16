from __future__ import annotations

import pandas as pd

from src.systems.food_inflation.processors.food_inflation_engine import (
    FOOD_INFLATION_OUTPUT_COLUMNS,
    build_food_inflation_engine,
)


FORBIDDEN_SCORE_COLUMNS = {
    "production_score",
    "inflation_pressure_score",
    "food_inflation_pressure_score",
    "composite_score",
}


def _monthly_fixture() -> pd.DataFrame:
    dates = pd.date_range("2025-01-31", periods=6, freq="ME")
    return pd.DataFrame(
        {
            "date": dates,
            "food_cpi": [100.0, 100.2, 100.5, 101.0, 101.6, 102.3],
            "food_at_home_cpi": [100.0, 100.1, 100.4, 100.8, 101.3, 101.9],
            "food_ppi": [100.0, 100.4, 100.9, 101.5, 102.4, 103.2],
            "wheat_price": [200.0, 202.0, 205.0, 212.0, 218.0, 225.0],
            "corn_price": [150.0, 151.0, 153.0, 158.0, 162.0, 166.0],
            "soybean_price": [300.0, 303.0, 309.0, 318.0, 326.0, 334.0],
            "rice_price": [500.0, 501.0, 503.0, 507.0, 512.0, 518.0],
            "beef_price": [250.0, 252.0, 255.0, 263.0, 270.0, 278.0],
            "meat_ppi": [110.0, 111.0, 112.0, 115.0, 117.0, 120.0],
        }
    )


def test_empty_input_returns_empty_full_schema() -> None:
    result = build_food_inflation_engine(pd.DataFrame())

    assert result.empty
    assert list(result.columns) == FOOD_INFLATION_OUTPUT_COLUMNS
    assert FORBIDDEN_SCORE_COLUMNS.isdisjoint(result.columns)


def test_missing_columns_do_not_crash_and_are_created_as_nan() -> None:
    input_df = pd.DataFrame(
        {
            "date": pd.date_range("2025-01-31", periods=4, freq="ME"),
            "food_cpi": [100.0, 100.1, 100.3, 100.6],
        }
    )

    result = build_food_inflation_engine(input_df, source_mode="official")

    assert list(result.columns) == FOOD_INFLATION_OUTPUT_COLUMNS
    assert result["wheat_price"].isna().all()
    assert result["corn_price"].isna().all()
    assert result["source_mode"].eq("official").all()
    assert result["missing_data_ratio"].between(0, 1).all()
    assert FORBIDDEN_SCORE_COLUMNS.isdisjoint(result.columns)


def test_monthly_fixture_produces_food_signals_after_enough_history() -> None:
    result = build_food_inflation_engine(_monthly_fixture(), source_mode="official")
    latest = result.iloc[-1]

    assert pd.notna(latest["grain_pressure"])
    assert pd.notna(latest["meat_protein_pressure"])
    assert pd.notna(latest["food_cpi_trend"])
    assert pd.notna(latest["food_ppi_pipeline_pressure"])
    assert pd.notna(latest["food_commodity_momentum"])
    assert latest["grain_pressure"] > 0
    assert latest["meat_protein_pressure"] > 0
    assert latest["food_cpi_trend"] > 0
    assert latest["food_ppi_pipeline_pressure"] > 0


def test_missing_data_ratio_and_source_confidence_are_row_level() -> None:
    frame = _monthly_fixture()
    frame.loc[frame.index[-1], ["wheat_price", "corn_price"]] = pd.NA

    result = build_food_inflation_engine(frame, source_mode="official")
    latest = result.iloc[-1]

    assert 0 < latest["missing_data_ratio"] < 1
    assert latest["source_confidence"] == 1 - latest["missing_data_ratio"]


def test_no_production_or_composite_score_columns_exist() -> None:
    result = build_food_inflation_engine(_monthly_fixture())

    assert FORBIDDEN_SCORE_COLUMNS.isdisjoint(result.columns)
