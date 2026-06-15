from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from oil_rate_macro_monitor.backtests.oil_signal_backtest import (
    REQUIRED_RESULT_FIELDS,
    run_oil_signal_backtest,
)


def _weekly_frame(rows: int = 40, include_curve: bool = True) -> pd.DataFrame:
    dates = pd.date_range("2025-01-03", periods=rows, freq="W-FRI")
    frame = pd.DataFrame(
        {
            "date": dates,
            "wti": [70 + index * 0.4 for index in range(rows)],
            "ten_year": [4.0 + index * 0.01 for index in range(rows)],
            "five_year_breakeven": [2.1 + index * 0.002 for index in range(rows)],
            "risk_asset_proxy": [100 + index * 0.7 for index in range(rows)],
            "oil_regime": ["supply_led_tightness" if index % 2 == 0 else "neutral_mixed" for index in range(rows)],
            "product_inventory_pressure": [
                "PRODUCT_TIGHTNESS" if index % 2 == 0 else "INVENTORY_BUILD_DEMAND_SOFTNESS"
                for index in range(rows)
            ],
            "oil_physical_tightness": ["PHYSICAL_TIGHT" if index % 2 == 0 else "INVENTORY_BUILD" for index in range(rows)],
            "macro_regime": ["inflation_pressure" if index % 2 == 0 else "neutral_mixed" for index in range(rows)],
        }
    )
    if include_curve:
        frame["wti_curve_state"] = ["BACKWARDATION" if index % 2 == 0 else "CONTANGO" for index in range(rows)]
    return frame


def _write_weekly_csv(tmp_path: Path, frame: pd.DataFrame) -> Path:
    input_path = tmp_path / "oil_rate_inflation_weekly_data.csv"
    frame.to_csv(input_path, index=False)
    return input_path


def test_missing_wti_curve_is_marked_missing_and_does_not_crash(tmp_path: Path) -> None:
    input_path = _write_weekly_csv(tmp_path, _weekly_frame(include_curve=False))
    output_path = tmp_path / "oil_signal_backtest_summary.json"

    summary = run_oil_signal_backtest(
        input_path=input_path,
        output_path=output_path,
        horizons_weeks=[4],
        min_samples=5,
    )

    curve_results = [item for item in summary["results"] if item["signal_name"] == "wti_curve_state"]
    assert curve_results
    assert all(item["missing_data_ratio"] == 1.0 for item in curve_results)
    assert all(item["usable_for_score"] is False for item in curve_results)
    assert output_path.exists()


def test_backtest_summary_schema_contains_required_fields_and_targets(tmp_path: Path) -> None:
    input_path = _write_weekly_csv(tmp_path, _weekly_frame())
    output_path = tmp_path / "oil_signal_backtest_summary.json"

    summary = run_oil_signal_backtest(
        input_path=input_path,
        output_path=output_path,
        horizons_weeks=[4, 8],
        min_samples=5,
    )

    assert summary["layer_type"] == "Supporting Research Layer"
    assert summary["production_scoring_changed"] is False
    assert summary["input_status"] == "OK"
    assert summary["results"]
    assert REQUIRED_RESULT_FIELDS.issubset(summary["results"][0])
    target_names = {item["target_name"] for item in summary["results"]}
    assert {
        "wti_forward_return",
        "ten_year_forward_change",
        "breakeven_inflation_forward_change",
        "risk_asset_proxy_forward_return",
    }.issubset(target_names)

    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved["results"][0]["usable_for_score"] in {True, False}


def test_insufficient_data_is_unusable_instead_of_scored(tmp_path: Path) -> None:
    input_path = _write_weekly_csv(tmp_path, _weekly_frame(rows=6))
    output_path = tmp_path / "oil_signal_backtest_summary.json"

    summary = run_oil_signal_backtest(
        input_path=input_path,
        output_path=output_path,
        horizons_weeks=[4],
        min_samples=10,
    )

    assert summary["results"]
    assert all(item["usable_for_score"] is False for item in summary["results"])
    assert all(item["suggested_direction"] == "INSUFFICIENT_DATA" for item in summary["results"])


def test_missing_legacy_output_path_discovers_processed_oil_and_rates(tmp_path: Path) -> None:
    system_root = tmp_path / "oil_rate_macro_monitor"
    processed_dir = system_root / "data" / "processed"
    processed_dir.mkdir(parents=True)
    frame = _weekly_frame(rows=40)
    frame[["date", "wti", "oil_regime", "product_inventory_pressure", "macro_regime"]].to_csv(
        processed_dir / "oil_engine.csv",
        index=False,
    )
    frame[["date", "ten_year"]].to_csv(processed_dir / "rates_curve.csv", index=False)

    summary = run_oil_signal_backtest(
        input_path=system_root / "output" / "oil_rate_inflation_weekly_data.csv",
        output_path=system_root / "exports" / "oil_signal_backtest_summary.json",
        horizons_weeks=[4],
        min_samples=5,
    )

    assert summary["input_status"] == "OK"
    assert summary["input_source"] == "processed_oil_and_rates"
    assert summary["results"]
    assert {item["target_name"] for item in summary["results"]} == {
        "wti_forward_return",
        "ten_year_forward_change",
    }
