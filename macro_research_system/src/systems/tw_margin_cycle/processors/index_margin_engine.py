from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.common.dates import today_taipei
from src.common.io import ensure_dir, repo_root, write_json
from src.systems.tw_margin_cycle.charts.index_margin_chart import (
    DETAILED_CYCLE_CHART_NAME,
    MAIN_CYCLE_CHART_NAME,
    ORIGINAL_STYLE_CHART_NAME,
    ORIGINAL_STYLE_RECENT5Y_CHART_NAME,
    PERCENT_CYCLE_CHART_NAME,
    RECENT5Y_CYCLE_CHART_NAME,
    RECENT5Y_PERCENT_CYCLE_CHART_NAME,
    write_index_margin_chart,
    write_original_style_chart,
    write_percent_cycle_chart,
    write_standardized_cycle_chart,
)
from src.systems.tw_margin_cycle.processors.data_quality import load_quality_flags
from src.systems.tw_margin_cycle.processors.signal_engine import classify_tw_margin_cycle
from src.systems.tw_margin_cycle.reports.tw_margin_cycle_report import write_tw_margin_cycle_report


def _mock_frame() -> pd.DataFrame:
    dates = pd.date_range("2026-05-01", periods=5, freq="B")
    return pd.DataFrame(
        {
            "date": dates,
            "index_close": [22000, 22500, 23000, 22800, 22600],
            "index_yoy": [0.20, 0.25, 0.30, 0.28, 0.26],
            "index_qoq": [0.10, 0.12, 0.14, 0.08, 0.05],
            "margin_balance_thousand_ntd": [300000000, 320000000, 340000000, 338000000, 330000000],
            "margin_roc": [0.25, 0.38, 0.48, 0.44, 0.30],
            "index_yoy_z": [1.0, 1.8, 2.3, 2.1, 1.5],
            "index_qoq_z": [1.0, 2.1, 2.4, 1.7, 1.0],
            "margin_roc_z": [1.2, 2.1, 2.5, 2.0, 1.1],
            "margin_roc_autocorr": [0.6, 0.7, 0.8, 0.75, 0.6],
            "margin_roc_persistence_score": [0.5, 0.7, 0.9, 0.8, 0.4],
            "raw_signal": ["NORMAL", "NORMAL", "NORMAL", "NORMAL", "NORMAL"],
        }
    )


def load_tw_margin_inputs(input_dir: Path | None = None) -> tuple[pd.DataFrame, dict[str, Any], list[str]]:
    root = repo_root()
    source_dir = input_dir or (root / "output")
    warnings: list[str] = []
    csv_path = source_dir / "tw_margin_autocorr_model.csv"
    summary_path = source_dir / "signal_summary.json"
    if csv_path.exists():
        frame = pd.read_csv(csv_path, parse_dates=["date"])
    else:
        frame = _mock_frame()
        warnings.append("Legacy TW margin CSV missing; using mock fixture data.")
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        summary = {}
        warnings.append("Legacy signal_summary.json missing; using derived mock summary.")
    return frame, summary, warnings


def _with_changes(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.sort_values("date").copy()
    if "margin_balance_percentile" not in out.columns:
        out["margin_balance_percentile"] = out["margin_balance_thousand_ntd"].rank(pct=True) * 100
    out["index_close_return_20d"] = out["index_close"].pct_change(20).fillna(0)
    out["index_close_return_60d"] = out["index_close"].pct_change(60).fillna(0)
    out["index_qoq_change_20d"] = out["index_qoq"].diff(20).fillna(out["index_qoq"].diff().fillna(0))
    out["margin_roc_change_20d"] = out["margin_roc"].diff(20).fillna(out["margin_roc"].diff().fillna(0))
    out["margin_balance_change_20d"] = (
        out["margin_balance_thousand_ntd"].diff(20).fillna(out["margin_balance_thousand_ntd"].diff().fillna(0))
    )
    return out


def build_tw_margin_cycle_summary(input_dir: Path | None = None) -> tuple[dict[str, Any], pd.DataFrame]:
    frame, legacy_summary, load_warnings = load_tw_margin_inputs(input_dir)
    frame = _with_changes(frame)
    latest = frame.iloc[-1].to_dict()
    source_dir = input_dir or (repo_root() / "output")
    data_quality_warning, market_extreme_report_warning, quality_warnings = load_quality_flags(source_dir)
    market_extreme_warning = bool(legacy_summary.get("market_extreme_warning", market_extreme_report_warning))
    latest["market_extreme_warning"] = market_extreme_warning
    if "raw_signal" not in latest:
        latest["raw_signal"] = legacy_summary.get("raw_signal", latest.get("signal", "NORMAL"))
    classified = classify_tw_margin_cycle(latest)
    warnings = load_warnings + quality_warnings
    mock_mode = any("mock" in item.lower() for item in load_warnings)
    summary = {
        "system": "tw_margin_cycle",
        "mock_mode": mock_mode,
        "report_date": today_taipei().isoformat(),
        "data_start": pd.to_datetime(frame["date"].min()).date().isoformat(),
        "data_end": pd.to_datetime(frame["date"].max()).date().isoformat(),
        "data_quality_warning": data_quality_warning,
        "market_extreme_warning": market_extreme_warning,
        "raw_signal": classified["raw_signal"],
        "final_signal": classified["final_signal"],
        "leverage_cycle_phase": classified["leverage_cycle_phase"],
        "risk_level": classified["risk_level"],
        "index_close": float(latest.get("index_close", 0.0)),
        "index_yoy": float(latest.get("index_yoy", 0.0)),
        "index_qoq": float(latest.get("index_qoq", 0.0)),
        "margin_balance_thousand_ntd": float(latest.get("margin_balance_thousand_ntd", 0.0)),
        "margin_balance_percentile": float(latest.get("margin_balance_percentile", 0.0)),
        "margin_roc": float(latest.get("margin_roc", 0.0)),
        "index_yoy_z": float(latest.get("index_yoy_z", 0.0)),
        "index_qoq_z": float(latest.get("index_qoq_z", 0.0)),
        "margin_roc_z": float(latest.get("margin_roc_z", 0.0)),
        "margin_roc_autocorr": float(latest.get("margin_roc_autocorr", 0.0)),
        "margin_roc_persistence_score": float(latest.get("margin_roc_persistence_score", 0.0)),
        "final_signal_reasons": classified["final_signal_reasons"],
        "transition_watch": classified["transition_watch"],
        "warnings": warnings,
    }
    return summary, frame


def run_tw_margin_cycle(data_root: Path) -> dict[str, Any]:
    summary, frame = build_tw_margin_cycle_summary()
    base = ensure_dir(data_root / "tw_margin_cycle")
    write_json(base / "processed" / "tw_margin_cycle_summary.json", summary)
    write_original_style_chart(frame, base / "charts" / ORIGINAL_STYLE_CHART_NAME)
    write_original_style_chart(frame, base / "charts" / ORIGINAL_STYLE_RECENT5Y_CHART_NAME, recent_years=5)
    write_percent_cycle_chart(frame, base / "charts" / PERCENT_CYCLE_CHART_NAME)
    write_percent_cycle_chart(frame, base / "charts" / RECENT5Y_PERCENT_CYCLE_CHART_NAME, recent_years=5)
    write_standardized_cycle_chart(frame, base / "charts" / MAIN_CYCLE_CHART_NAME)
    write_standardized_cycle_chart(frame, base / "charts" / RECENT5Y_CYCLE_CHART_NAME, recent_years=5)
    write_index_margin_chart(frame, base / "charts" / DETAILED_CYCLE_CHART_NAME)
    write_tw_margin_cycle_report(summary, base / "reports")
    return summary
