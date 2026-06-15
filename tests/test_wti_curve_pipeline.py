from __future__ import annotations

from pathlib import Path

import pandas as pd

from oil_rate_macro_monitor.backtests.oil_signal_backtest import run_oil_signal_backtest
from oil_rate_macro_monitor.src.fetchers.wti_curve_fetcher import (
    fetch_wti_curve_api,
    standardize_wti_curve_frame,
)
from oil_rate_macro_monitor.src.processors.oil_curve import calculate_oil_curve


def test_missing_wti_curve_api_credentials_return_empty_contract_frame() -> None:
    result = fetch_wti_curve_api(api_url=None, api_key=None)

    assert result.empty
    assert list(result.columns) == [
        "date",
        "cl_m1_settle",
        "cl_m2_settle",
        "cl_m3_settle",
        "source",
        "source_type",
    ]


def test_yahoo_front_month_cannot_be_standardized_as_wti_curve() -> None:
    yahoo_front_month = pd.DataFrame(
        {
            "date": ["2026-01-02"],
            "ticker": ["CL=F"],
            "close": [75.0],
        }
    )

    result = standardize_wti_curve_frame(
        yahoo_front_month,
        source="Yahoo CL=F",
        source_type="research_manual",
    )

    assert result.empty


def test_oil_curve_calculates_states_from_formal_contract_ladder() -> None:
    curve_input = pd.DataFrame(
        {
            "date": ["2026-01-02", "2026-01-09", "2026-01-16"],
            "wti": [75.0, 74.0, 73.0],
            "brent": [78.0, 77.0, 76.0],
            "cl_m1_settle": [76.00, 74.00, 75.00],
            "cl_m2_settle": [75.50, 74.40, 74.95],
            "cl_m3_settle": [75.00, 74.80, 74.90],
            "source": ["test_vendor"] * 3,
            "source_type": ["production_api"] * 3,
        }
    )

    result = calculate_oil_curve(curve_input)

    assert list(result["curve_state"]) == ["backwardation", "contango", "flat"]
    assert list(result["m1_m2_spread"].round(2)) == [0.50, -0.40, 0.05]
    assert list(result["m1_m3_spread"].round(2)) == [1.00, -0.80, 0.10]


def test_backtest_discovers_processed_oil_curve_state(tmp_path: Path) -> None:
    system_root = tmp_path / "oil_rate_macro_monitor"
    processed_dir = system_root / "data" / "processed"
    processed_dir.mkdir(parents=True)
    dates = pd.date_range("2025-01-03", periods=40, freq="W-FRI")
    oil = pd.DataFrame(
        {
            "date": dates,
            "wti": [70 + index * 0.2 for index in range(len(dates))],
            "oil_regime": ["neutral_mixed"] * len(dates),
        }
    )
    rates = pd.DataFrame(
        {
            "date": dates,
            "ten_year": [4.0 + index * 0.01 for index in range(len(dates))],
        }
    )
    oil_curve = pd.DataFrame(
        {
            "date": dates,
            "m1_m2_spread": [0.4 if index % 2 == 0 else -0.4 for index in range(len(dates))],
            "m1_m3_spread": [0.8 if index % 2 == 0 else -0.8 for index in range(len(dates))],
            "curve_state": ["backwardation" if index % 2 == 0 else "contango" for index in range(len(dates))],
            "source": ["test_vendor"] * len(dates),
            "source_type": ["production_api"] * len(dates),
        }
    )
    oil.to_csv(processed_dir / "oil_engine.csv", index=False)
    rates.to_csv(processed_dir / "rates_curve.csv", index=False)
    oil_curve.to_csv(processed_dir / "oil_curve.csv", index=False)

    summary = run_oil_signal_backtest(
        input_path=system_root / "output" / "oil_rate_inflation_weekly_data.csv",
        output_path=system_root / "exports" / "oil_signal_backtest_summary.json",
        horizons_weeks=[4],
        min_samples=5,
    )

    curve_results = [item for item in summary["results"] if item["signal_name"] == "wti_curve_state"]
    diagnostics = {item["signal_name"]: item for item in summary["feature_diagnostics"]}

    assert curve_results
    assert all(item["missing_data_ratio"] < 1.0 for item in curve_results)
    assert diagnostics["wti_curve_state"]["non_null_count"] > 0
    assert "oil_curve.csv" in " ".join(summary["resolved_input_paths"])


def test_no_energy_oil_production_score_function_exists() -> None:
    root = Path(__file__).resolve().parents[1]
    python_files = [
        path
        for path in (root / "oil_rate_macro_monitor").rglob("*.py")
        if "backtests" not in path.parts and "__pycache__" not in path.parts
    ]

    forbidden_terms = [
        "energy_oil_inflation_pressure_score",
        "def calculate_production_score",
        "def build_production_score",
    ]

    for path in python_files:
        text = path.read_text(encoding="utf-8")
        assert not any(term in text for term in forbidden_terms), path
