from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_HORIZONS_MONTHS = [1, 3, 6, 12]
MIN_SAMPLE_COUNT = 24
MAX_TARGET_MISSING_RATIO = 0.80

SIGNAL_SPECS = {
    "shelter_cpi_trend": {
        "feature_role": "candidate_signal",
        "source_columns": ["shelter_cpi_trend"],
    },
    "rent_pressure": {
        "feature_role": "candidate_signal",
        "source_columns": ["rent_pressure"],
    },
    "oer_pressure": {
        "feature_role": "candidate_signal",
        "source_columns": ["oer_pressure"],
    },
    "home_price_momentum": {
        "feature_role": "candidate_signal",
        "source_columns": ["home_price_momentum"],
    },
    "mortgage_rate_pressure": {
        "feature_role": "candidate_signal",
        "source_columns": ["mortgage_rate_pressure"],
    },
    "housing_activity_pressure": {
        "feature_role": "candidate_signal",
        "source_columns": ["housing_activity_pressure"],
    },
    "affordability_stress": {
        "feature_role": "candidate_signal",
        "source_columns": ["affordability_stress"],
    },
    "shelter_pipeline_pressure": {
        "feature_role": "candidate_signal",
        "source_columns": ["shelter_pipeline_pressure"],
    },
    "source_confidence": {
        "feature_role": "diagnostic_only",
        "source_columns": ["source_confidence", "missing_data_ratio"],
    },
}

TARGET_SPECS = {
    "shelter_cpi_forward_change": {
        "source_columns": ["shelter_cpi", "shelter_cpi_sa"],
        "method": "pct_change",
    },
    "headline_cpi_forward_change": {
        "source_columns": ["headline_cpi"],
        "method": "pct_change",
    },
    "core_cpi_forward_change": {
        "source_columns": ["core_cpi"],
        "method": "pct_change",
    },
    "breakeven_inflation_forward_change": {
        "source_columns": ["breakeven_inflation"],
        "method": "diff",
    },
    "rates_forward_change": {
        "source_columns": ["rates_level"],
        "method": "diff",
    },
    "risk_asset_proxy_forward_drawdown": {
        "source_columns": ["risk_asset_proxy"],
        "method": "drawdown",
    },
}

REQUIRED_SUMMARY_FIELDS = {
    "signal_name",
    "target_name",
    "horizon_months",
    "sample_count",
    "hit_rate",
    "information_coefficient",
    "missing_data_ratio",
    "target_missing_data_ratio",
    "suggested_direction",
    "suggested_weight_range",
    "usable_for_score",
    "unusable_reason",
    "source_columns",
    "feature_role",
}


def run_shelter_signal_backtest(
    input_df: pd.DataFrame,
    horizons_months: list[int] | None = None,
) -> list[dict[str, Any]]:
    horizons = horizons_months or DEFAULT_HORIZONS_MONTHS
    frame = _prepare_frame(input_df)
    results: list[dict[str, Any]] = []
    for signal_name, signal_spec in SIGNAL_SPECS.items():
        signal = _numeric_column(frame, signal_name)
        signal_missing_ratio = _missing_ratio(signal, len(frame))
        for target_name, target_spec in TARGET_SPECS.items():
            for horizon in horizons:
                target, target_available = _build_forward_target(
                    frame,
                    target_spec["source_columns"],
                    target_spec["method"],
                    horizon,
                )
                results.append(
                    _evaluate_signal_target(
                        signal_name=signal_name,
                        signal=signal,
                        signal_missing_ratio=signal_missing_ratio,
                        signal_spec=signal_spec,
                        target_name=target_name,
                        target=target,
                        target_missing_ratio=_missing_ratio(target, len(frame)),
                        target_available=target_available,
                        horizon_months=horizon,
                    )
                )
    return results


def write_shelter_backtest_summary(summary: list[dict[str, Any]], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _prepare_frame(input_df: pd.DataFrame) -> pd.DataFrame:
    frame = input_df.copy()
    if "date" not in frame.columns:
        frame["date"] = pd.NaT
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    return frame.sort_values("date").reset_index(drop=True)


def _numeric_column(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def _build_forward_target(
    frame: pd.DataFrame,
    source_columns: list[str],
    method: str,
    horizon: int,
) -> tuple[pd.Series, bool]:
    source_column = next((column for column in source_columns if column in frame.columns), None)
    if source_column is None:
        return pd.Series(np.nan, index=frame.index, dtype="float64"), False
    series = pd.to_numeric(frame[source_column], errors="coerce")
    if method == "pct_change":
        return series.shift(-horizon) / series - 1, True
    if method == "diff":
        return series.shift(-horizon) - series, True
    if method == "drawdown":
        return _forward_drawdown(series, horizon), True
    raise ValueError(f"Unsupported target method: {method}")


def _forward_drawdown(series: pd.Series, horizon: int) -> pd.Series:
    values = []
    for index, current in series.items():
        if pd.isna(current) or current == 0:
            values.append(np.nan)
            continue
        forward_window = series.iloc[index + 1 : index + horizon + 1]
        if forward_window.empty or forward_window.isna().all():
            values.append(np.nan)
            continue
        values.append(forward_window.min() / current - 1)
    return pd.Series(values, index=series.index, dtype="float64")


def _evaluate_signal_target(
    signal_name: str,
    signal: pd.Series,
    signal_missing_ratio: float,
    signal_spec: dict[str, Any],
    target_name: str,
    target: pd.Series,
    target_missing_ratio: float,
    target_available: bool,
    horizon_months: int,
) -> dict[str, Any]:
    valid = signal.notna() & target.notna()
    sample_count = int(valid.sum())
    ic = _pearson(signal[valid], target[valid])
    hit_rate = _hit_rate(signal[valid], target[valid])
    feature_role = signal_spec["feature_role"]
    unusable_reason = _unusable_reason(
        feature_role=feature_role,
        target_available=target_available,
        sample_count=sample_count,
        target_missing_ratio=target_missing_ratio,
    )
    usable_for_score = unusable_reason is None
    return {
        "signal_name": signal_name,
        "target_name": target_name,
        "horizon_months": int(horizon_months),
        "sample_count": sample_count,
        "hit_rate": hit_rate,
        "information_coefficient": ic,
        "missing_data_ratio": signal_missing_ratio,
        "target_missing_data_ratio": target_missing_ratio,
        "suggested_direction": _suggested_direction(ic, usable_for_score),
        "suggested_weight_range": _suggested_weight_range(usable_for_score, feature_role),
        "usable_for_score": usable_for_score,
        "unusable_reason": unusable_reason,
        "source_columns": signal_spec["source_columns"],
        "feature_role": feature_role,
    }


def _unusable_reason(
    feature_role: str,
    target_available: bool,
    sample_count: int,
    target_missing_ratio: float,
) -> str | None:
    if feature_role == "diagnostic_only":
        return "DIAGNOSTIC_ONLY"
    if not target_available:
        return "MISSING_TARGET"
    if target_missing_ratio > MAX_TARGET_MISSING_RATIO:
        return "HIGH_MISSING_RATIO"
    if sample_count < MIN_SAMPLE_COUNT:
        return "INSUFFICIENT_DATA"
    return None


def _missing_ratio(series: pd.Series, row_count: int) -> float:
    if row_count == 0:
        return 1.0
    return float(series.isna().mean())


def _pearson(signal: pd.Series, target: pd.Series) -> float | None:
    if len(signal) < 2 or signal.nunique(dropna=True) < 2 or target.nunique(dropna=True) < 2:
        return None
    value = signal.corr(target)
    if pd.isna(value):
        return None
    return float(value)


def _hit_rate(signal: pd.Series, target: pd.Series) -> float | None:
    if len(signal) == 0:
        return None
    signal_direction = np.sign(signal)
    target_direction = np.sign(target)
    directional = (signal_direction != 0) & (target_direction != 0)
    if not directional.any():
        return None
    return float((signal_direction[directional] == target_direction[directional]).mean())


def _suggested_direction(ic: float | None, usable_for_score: bool) -> str:
    if not usable_for_score or ic is None:
        return "unknown"
    if ic > 0:
        return "positive"
    if ic < 0:
        return "negative"
    return "unknown"


def _suggested_weight_range(usable_for_score: bool, feature_role: str) -> str | None:
    if not usable_for_score or feature_role == "diagnostic_only":
        return None
    return "0-0.05"
