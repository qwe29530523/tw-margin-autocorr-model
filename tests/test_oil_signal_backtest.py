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
    assert summary["unavailable_targets"] == []
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


def test_backtest_uses_processed_breakeven_5y_as_forward_change_target(tmp_path: Path) -> None:
    frame = _weekly_frame(rows=40).drop(columns=["five_year_breakeven"])
    frame["breakeven_5y"] = [2.1 + index * 0.002 for index in range(len(frame))]
    input_path = _write_weekly_csv(tmp_path, frame)
    output_path = tmp_path / "oil_signal_backtest_summary.json"

    summary = run_oil_signal_backtest(
        input_path=input_path,
        output_path=output_path,
        horizons_weeks=[4],
        min_samples=5,
    )

    target_names = {item["target_name"] for item in summary["results"]}
    unavailable_target_names = {item["target_name"] for item in summary["unavailable_targets"]}
    breakeven_results = [
        item for item in summary["results"] if item["target_name"] == "breakeven_inflation_forward_change"
    ]
    diagnostics = {item["signal_name"]: item for item in summary["feature_diagnostics"]}

    assert "breakeven_inflation_forward_change" in target_names
    assert "breakeven_inflation_forward_change" not in unavailable_target_names
    assert breakeven_results
    assert all(item["sample_count"] > 0 for item in breakeven_results)
    assert "breakeven_5y" in diagnostics["source_confidence"]["available_source_columns"]


def test_backtest_uses_processed_breakeven_10y_as_fallback_target(tmp_path: Path) -> None:
    frame = _weekly_frame(rows=40).drop(columns=["five_year_breakeven"])
    frame["breakeven_10y"] = [2.3 + index * 0.001 for index in range(len(frame))]
    input_path = _write_weekly_csv(tmp_path, frame)
    output_path = tmp_path / "oil_signal_backtest_summary.json"

    summary = run_oil_signal_backtest(
        input_path=input_path,
        output_path=output_path,
        horizons_weeks=[4],
        min_samples=5,
    )

    target_names = {item["target_name"] for item in summary["results"]}
    unavailable_target_names = {item["target_name"] for item in summary["unavailable_targets"]}

    assert "breakeven_inflation_forward_change" in target_names
    assert "breakeven_inflation_forward_change" not in unavailable_target_names


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
    unavailable_target_names = {item["target_name"] for item in summary["unavailable_targets"]}
    assert {
        "breakeven_inflation_forward_change",
        "risk_asset_proxy_forward_return",
    }.issubset(unavailable_target_names)


def test_physical_tightness_can_be_derived_from_inventory_refinery_and_exports(tmp_path: Path) -> None:
    frame = _weekly_frame(rows=40).drop(columns=["oil_physical_tightness"])
    frame["gasoline_inventory_4w_change"] = [-3 if index % 2 == 0 else 4 for index in range(len(frame))]
    frame["distillate_inventory_4w_change"] = [-2 if index % 2 == 0 else 3 for index in range(len(frame))]
    frame["refinery_utilization_4w_change"] = [1 if index % 2 == 0 else -1 for index in range(len(frame))]
    frame["crude_inventory_4w_change"] = [-5 if index % 3 == 0 else 6 for index in range(len(frame))]
    frame["crude_exports_4w_change"] = [2 if index % 3 == 0 else -1 for index in range(len(frame))]
    frame["total_inventory_proxy_4w_change"] = [8 if index % 2 else -8 for index in range(len(frame))]
    input_path = _write_weekly_csv(tmp_path, frame)

    summary = run_oil_signal_backtest(
        input_path=input_path,
        output_path=tmp_path / "oil_signal_backtest_summary.json",
        horizons_weeks=[4],
        min_samples=5,
    )

    physical_results = [item for item in summary["results"] if item["signal_name"] == "physical_tightness"]
    assert physical_results
    assert all(item["missing_data_ratio"] == 0.0 for item in physical_results)
    assert all(item["sample_count"] > 0 for item in physical_results)


def test_feature_diagnostics_separate_physical_and_product_pressure(tmp_path: Path) -> None:
    frame = _weekly_frame(rows=40).drop(columns=["oil_physical_tightness", "product_inventory_pressure"])
    frame["crude_inventory_4w_change"] = [-5 if index % 3 == 0 else 6 for index in range(len(frame))]
    frame["gasoline_inventory_4w_change"] = [-3 if index % 2 == 0 else 4 for index in range(len(frame))]
    frame["distillate_inventory_4w_change"] = [-2 if index % 2 == 0 else 3 for index in range(len(frame))]
    frame["total_inventory_proxy_4w_change"] = frame[
        ["crude_inventory_4w_change", "gasoline_inventory_4w_change", "distillate_inventory_4w_change"]
    ].sum(axis=1)
    frame["refinery_utilization_4w_change"] = [1 if index % 2 == 0 else -1 for index in range(len(frame))]
    frame["crude_exports_4w_change"] = [2 if index % 3 == 0 else -1 for index in range(len(frame))]
    frame["crude_production_4w_change"] = [1 if index % 4 == 0 else -1 for index in range(len(frame))]
    frame["product_demand_signal"] = [
        "product_demand_diesel_led" if index % 2 == 0 else "broad_product_demand_softening"
        for index in range(len(frame))
    ]
    input_path = _write_weekly_csv(tmp_path, frame)

    summary = run_oil_signal_backtest(
        input_path=input_path,
        output_path=tmp_path / "oil_signal_backtest_summary.json",
        horizons_weeks=[4],
        min_samples=5,
    )

    diagnostics = {item["signal_name"]: item for item in summary["feature_diagnostics"]}
    physical = diagnostics["physical_tightness"]
    product = diagnostics["product_inventory_pressure"]
    assert physical["duplicate_of"] is None
    assert product["duplicate_of"] is None
    assert physical["raw_equals_product_inventory_pressure"] is False
    assert product["raw_equals_physical_tightness"] is False
    assert "crude_inventory_4w_change" in physical["source_columns"]
    assert "crude_exports_4w_change" in physical["source_columns"]
    assert "gasoline_inventory_4w_change" in product["source_columns"]
    assert "distillate_inventory_4w_change" in product["source_columns"]
    assert "product_demand_signal" in product["source_columns"]
