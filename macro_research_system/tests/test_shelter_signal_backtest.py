from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.systems.shelter_inflation.backtests.shelter_signal_backtest import (
    DEFAULT_HORIZONS_MONTHS,
    REQUIRED_SUMMARY_FIELDS,
    run_shelter_signal_backtest,
    write_shelter_backtest_summary,
)


FORBIDDEN_SCORE_NAMES = {
    "production_score",
    "inflation_pressure_score",
    "shelter_inflation_pressure_score",
    "composite_score",
}


def _monthly_shelter_frame(rows: int = 48) -> pd.DataFrame:
    dates = pd.date_range("2021-01-31", periods=rows, freq="ME")
    return pd.DataFrame(
        {
            "date": dates,
            "shelter_cpi": [100 + index * 0.34 for index in range(rows)],
            "shelter_cpi_sa": [100 + index * 0.33 for index in range(rows)],
            "headline_cpi": [100 + index * 0.30 for index in range(rows)],
            "core_cpi": [100 + index * 0.28 for index in range(rows)],
            "breakeven_inflation": [2.0 + index * 0.004 for index in range(rows)],
            "rates_level": [3.0 + index * 0.008 for index in range(rows)],
            "risk_asset_proxy": [100 + index * 0.35 - (5 if index % 11 == 0 else 0) for index in range(rows)],
            "shelter_cpi_trend": [0.004 if index % 2 == 0 else -0.001 for index in range(rows)],
            "rent_pressure": [0.005 if index % 2 == 0 else -0.0015 for index in range(rows)],
            "oer_pressure": [0.0045 if index % 3 == 0 else -0.001 for index in range(rows)],
            "home_price_momentum": [0.012 if index % 2 == 0 else -0.003 for index in range(rows)],
            "mortgage_rate_pressure": [0.08 if index % 2 == 0 else -0.04 for index in range(rows)],
            "housing_activity_pressure": [0.01 if index % 2 == 0 else -0.004 for index in range(rows)],
            "affordability_stress": [0.02 if index % 3 == 0 else -0.006 for index in range(rows)],
            "shelter_pipeline_pressure": [0.014 if index % 2 == 0 else -0.004 for index in range(rows)],
            "source_confidence": [0.9] * rows,
            "missing_data_ratio": [0.1] * rows,
        }
    )


def _assert_no_forbidden_score_names(payload: object) -> None:
    text = str(payload)
    for name in FORBIDDEN_SCORE_NAMES:
        assert name not in text


def test_empty_input_does_not_crash_and_marks_missing_targets() -> None:
    summary = run_shelter_signal_backtest(pd.DataFrame())

    assert summary
    assert all(REQUIRED_SUMMARY_FIELDS.issubset(item) for item in summary)
    assert all(item["usable_for_score"] is False for item in summary)
    assert all(item["unusable_reason"] in {"MISSING_TARGET", "INSUFFICIENT_DATA", "DIAGNOSTIC_ONLY"} for item in summary)
    _assert_no_forbidden_score_names(summary)


def test_missing_targets_are_unusable_without_crashing() -> None:
    frame = _monthly_shelter_frame().drop(
        columns=["shelter_cpi", "shelter_cpi_sa", "headline_cpi", "core_cpi", "breakeven_inflation", "rates_level", "risk_asset_proxy"]
    )

    summary = run_shelter_signal_backtest(frame, horizons_months=[1])

    assert summary
    assert all(item["sample_count"] == 0 for item in summary)
    assert all(item["usable_for_score"] is False for item in summary)
    assert all(
        item["unusable_reason"] == "MISSING_TARGET"
        for item in summary
        if item["signal_name"] != "source_confidence"
    )
    assert all(
        item["unusable_reason"] == "DIAGNOSTIC_ONLY"
        for item in summary
        if item["signal_name"] == "source_confidence"
    )


def test_synthetic_monthly_fixture_produces_complete_summary_schema() -> None:
    summary = run_shelter_signal_backtest(_monthly_shelter_frame(), horizons_months=[1, 3, 6, 12])

    assert summary
    assert all(REQUIRED_SUMMARY_FIELDS.issubset(item) for item in summary)
    signal_names = {item["signal_name"] for item in summary}
    target_names = {item["target_name"] for item in summary}
    assert {
        "shelter_cpi_trend",
        "rent_pressure",
        "oer_pressure",
        "home_price_momentum",
        "mortgage_rate_pressure",
        "housing_activity_pressure",
        "affordability_stress",
        "shelter_pipeline_pressure",
        "source_confidence",
    }.issubset(signal_names)
    assert {
        "shelter_cpi_forward_change",
        "headline_cpi_forward_change",
        "core_cpi_forward_change",
        "breakeven_inflation_forward_change",
        "rates_forward_change",
        "risk_asset_proxy_forward_drawdown",
    }.issubset(target_names)
    assert any(item["sample_count"] >= 24 for item in summary)
    _assert_no_forbidden_score_names(summary)


def test_feature_roles_and_diagnostic_only_source_confidence() -> None:
    summary = run_shelter_signal_backtest(_monthly_shelter_frame(), horizons_months=[1])

    source_confidence_results = [item for item in summary if item["signal_name"] == "source_confidence"]
    candidate_results = [item for item in summary if item["signal_name"] != "source_confidence"]

    assert source_confidence_results
    assert all(item["feature_role"] == "diagnostic_only" for item in source_confidence_results)
    assert all(item["usable_for_score"] is False for item in source_confidence_results)
    assert all(item["suggested_weight_range"] is None for item in source_confidence_results)
    assert all(item["unusable_reason"] == "DIAGNOSTIC_ONLY" for item in source_confidence_results)
    assert candidate_results
    assert all(item["feature_role"] == "candidate_signal" for item in candidate_results)


def test_insufficient_data_gate_keeps_results_unusable() -> None:
    summary = run_shelter_signal_backtest(_monthly_shelter_frame(rows=12), horizons_months=[1])

    assert summary
    assert all(item["usable_for_score"] is False for item in summary)
    assert all(item["unusable_reason"] in {"INSUFFICIENT_DATA", "DIAGNOSTIC_ONLY"} for item in summary)


def test_default_horizons_include_shelter_lag_windows() -> None:
    assert DEFAULT_HORIZONS_MONTHS == [1, 3, 6, 12]

    summary = run_shelter_signal_backtest(_monthly_shelter_frame())
    horizons = {item["horizon_months"] for item in summary}

    assert {1, 3, 6, 12}.issubset(horizons)


def test_optional_writer_uses_explicit_path_and_does_not_create_production_score_json(tmp_path: Path) -> None:
    summary = run_shelter_signal_backtest(_monthly_shelter_frame(), horizons_months=[1])
    output_path = tmp_path / "shelter_signal_backtest_summary.json"

    written = write_shelter_backtest_summary(summary, output_path)

    assert written == output_path
    assert output_path.exists()
    _assert_no_forbidden_score_names(output_path.read_text(encoding="utf-8"))
    repo_output = Path("macro_research_system/data/shelter_inflation/backtests/shelter_signal_backtest_summary.json")
    assert not repo_output.exists()
