from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_PATH = BASE_DIR / "output" / "oil_rate_inflation_weekly_data.csv"
DEFAULT_OUTPUT_PATH = BASE_DIR / "exports" / "oil_signal_backtest_summary.json"
DEFAULT_HORIZONS_WEEKS = [4, 8, 13]
DEFAULT_MIN_SAMPLES = 20

REQUIRED_RESULT_FIELDS = {
    "signal_name",
    "target_name",
    "horizon_weeks",
    "sample_count",
    "hit_rate",
    "average_forward_return",
    "median_forward_return",
    "average_forward_drawdown",
    "information_coefficient",
    "missing_data_ratio",
    "suggested_direction",
    "suggested_weight_range",
    "usable_for_score",
}


def run_oil_signal_backtest(
    input_path: str | Path | None = None,
    output_path: str | Path | None = None,
    horizons_weeks: list[int] | None = None,
    min_samples: int = DEFAULT_MIN_SAMPLES,
) -> dict[str, Any]:
    source_path = Path(input_path) if input_path is not None else DEFAULT_INPUT_PATH
    destination_path = Path(output_path) if output_path is not None else DEFAULT_OUTPUT_PATH
    horizons = horizons_weeks or DEFAULT_HORIZONS_WEEKS

    input_data = _load_weekly_input(source_path)
    if input_data["status"] != "OK":
        summary = _base_summary(source_path, horizons, input_data["status"])
        summary["input_source"] = input_data["source"]
        summary["resolved_input_paths"] = input_data["paths"]
        summary["notes"].extend(input_data["notes"])
        _write_json(destination_path, summary)
        return summary

    weekly = input_data["frame"]
    if weekly.empty:
        summary = _base_summary(source_path, horizons, "INSUFFICIENT_DATA")
        summary["input_source"] = input_data["source"]
        summary["resolved_input_paths"] = input_data["paths"]
        summary["notes"].append("Input weekly data file is empty; all signals are unusable for scoring.")
        _write_json(destination_path, summary)
        return summary

    weekly = _prepare_weekly_frame(weekly)
    signals = _build_signal_features(weekly)
    targets = _build_forward_targets(weekly, horizons)

    summary = _base_summary(source_path, horizons, "OK")
    summary["input_source"] = input_data["source"]
    summary["resolved_input_paths"] = input_data["paths"]
    summary["notes"].extend(input_data["notes"])
    summary["row_count"] = int(len(weekly))
    summary["date_range"] = _date_range(weekly)
    summary["signal_names"] = list(signals.keys())
    summary["target_names"] = sorted({target["target_name"] for target in targets})
    summary["results"] = [
        _evaluate_signal_target(
            signal_name=signal_name,
            signal=signal,
            target=target,
            min_samples=min_samples,
        )
        for signal_name, signal in signals.items()
        for target in targets
    ]
    if not summary["results"]:
        summary["input_status"] = "INSUFFICIENT_DATA"
        summary["notes"].append("No computable forward targets were found; no production score was changed.")

    _write_json(destination_path, summary)
    return summary


def _base_summary(source_path: Path, horizons: list[int], input_status: str) -> dict[str, Any]:
    return {
        "system": "oil_rate_macro_monitor",
        "layer": "oil_signal_backtest",
        "layer_type": "Supporting Research Layer",
        "production_scoring_changed": False,
        "input_path": str(source_path),
        "input_status": input_status,
        "input_source": None,
        "resolved_input_paths": [],
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "horizons_weeks": horizons,
        "target_names": [],
        "signal_names": [],
        "results": [],
        "notes": [
            "Backtest output is research evidence only and must not be treated as production scoring.",
            "WTI futures curve gaps are kept as missing; no curve data is forward filled or fabricated.",
        ],
    }


def _load_weekly_input(source_path: Path) -> dict[str, Any]:
    if source_path.exists():
        return {
            "status": "OK",
            "source": "weekly_csv",
            "paths": [str(source_path)],
            "frame": pd.read_csv(source_path),
            "notes": [],
        }

    system_root = _infer_system_root(source_path)
    processed = _load_processed_oil_and_rates(system_root)
    if not processed.empty:
        return {
            "status": "OK",
            "source": "processed_oil_and_rates",
            "paths": processed.attrs.get("source_paths", []),
            "frame": processed,
            "notes": [
                "Requested weekly CSV was missing; backtest loaded existing processed oil_engine/rates_curve outputs.",
                "Processed daily frames were resampled to W-FRI using the last valid observation in each week.",
            ],
        }

    return {
        "status": "MISSING",
        "source": "missing",
        "paths": [],
        "frame": pd.DataFrame(),
        "notes": ["Input weekly data file is missing and no processed oil/rates fallback was found; no production score was changed."],
    }


def _infer_system_root(source_path: Path) -> Path:
    for candidate in [source_path.parent, *source_path.parents]:
        if candidate.name == "oil_rate_macro_monitor":
            return candidate
    return BASE_DIR


def _load_processed_oil_and_rates(system_root: Path) -> pd.DataFrame:
    processed_dir = system_root / "data" / "processed"
    oil_path, oil = _read_processed_frame(processed_dir, "oil_engine")
    rates_path, rates = _read_processed_frame(processed_dir, "rates_curve")
    if oil.empty and rates.empty:
        return pd.DataFrame()
    if oil.empty:
        merged = rates.copy()
    elif rates.empty:
        merged = oil.copy()
    else:
        merged = pd.merge(oil, rates, on="date", how="outer", suffixes=("", "_rates"))
    weekly = _to_weekly(merged)
    weekly.attrs["source_paths"] = [str(path) for path in [oil_path, rates_path] if path is not None]
    return weekly


def _read_processed_frame(processed_dir: Path, stem: str) -> tuple[Path | None, pd.DataFrame]:
    parquet_path = processed_dir / f"{stem}.parquet"
    csv_path = processed_dir / f"{stem}.csv"
    if parquet_path.exists():
        try:
            return parquet_path, pd.read_parquet(parquet_path)
        except Exception:  # noqa: BLE001
            pass
    if csv_path.exists():
        return csv_path, pd.read_csv(csv_path)
    return None, pd.DataFrame()


def _to_weekly(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "date" not in frame.columns:
        return frame.copy()
    out = frame.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date"]).sort_values("date")
    if out.empty:
        return out
    out = out.set_index("date").resample("W-FRI").last().dropna(how="all").reset_index()
    return out


def _prepare_weekly_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
        out = out.sort_values("date").reset_index(drop=True)
    return out


def _build_signal_features(frame: pd.DataFrame) -> dict[str, pd.Series]:
    return {
        "oil_price_momentum": _oil_price_momentum_signal(frame),
        "oil_price_regime": _mapped_text_signal(_first_existing(frame, ["oil_regime", "oil_price_regime"]), _oil_regime_score, frame.index),
        "wti_curve_state": _mapped_text_signal(_first_existing(frame, ["wti_curve_state", "curve_state"]), _curve_state_score, frame.index),
        "physical_tightness": _mapped_text_signal(
            _first_existing(frame, ["oil_physical_tightness", "physical_tightness_signal"]),
            _physical_tightness_score,
            frame.index,
        ),
        "product_inventory_pressure": _mapped_text_signal(
            _first_existing(frame, ["product_inventory_pressure", "inventory_signal"]),
            _product_inventory_score,
            frame.index,
        ),
        "inflation_rates_transmission": _mapped_text_signal(
            _first_existing(frame, ["oil_rate_mix", "macro_regime", "rates_regime", "rate_signal"]),
            _inflation_rates_score,
            frame.index,
        ),
        "source_confidence": _source_confidence_signal(frame),
    }


def _build_forward_targets(frame: pd.DataFrame, horizons: list[int]) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    target_specs = [
        ("wti_forward_return", ["wti", "wti_close", "wti_price"], "return"),
        ("ten_year_forward_change", ["ten_year", "ten_year_yield", "DGS10"], "change"),
        (
            "breakeven_inflation_forward_change",
            ["five_year_breakeven", "breakeven_inflation", "five_year_breakeven_inflation", "breakeven_5y", "T5YIE"],
            "change",
        ),
        ("risk_asset_proxy_forward_return", ["risk_asset_proxy", "spx", "spy", "equity_proxy"], "return"),
    ]
    for target_name, candidates, method in target_specs:
        series = _numeric_first_existing(frame, candidates)
        if series is None:
            continue
        for horizon in horizons:
            target = _forward_return(series, horizon) if method == "return" else _forward_change(series, horizon)
            drawdown = _forward_drawdown(series, horizon) if target_name == "risk_asset_proxy_forward_return" else None
            targets.append(
                {
                    "target_name": target_name,
                    "horizon_weeks": int(horizon),
                    "values": target,
                    "drawdown": drawdown,
                }
            )
    return targets


def _evaluate_signal_target(
    signal_name: str,
    signal: pd.Series,
    target: dict[str, Any],
    min_samples: int,
) -> dict[str, Any]:
    target_values = target["values"]
    drawdown = target.get("drawdown")
    missing_data_ratio = float(signal.isna().mean()) if len(signal) else 1.0
    active = signal.notna() & target_values.notna() & (signal != 0)
    sample_count = int(active.sum())
    signed_target = target_values[active] * signal[active] if sample_count else pd.Series(dtype=float)
    information_coefficient = _information_coefficient(signal, target_values, active)

    insufficient = sample_count < min_samples
    suggested_direction = _suggested_direction(signed_target, insufficient)
    usable_for_score = (
        not insufficient
        and missing_data_ratio <= 0.5
        and suggested_direction in {"POSITIVE", "NEGATIVE"}
    )
    result = {
        "signal_name": signal_name,
        "target_name": target["target_name"],
        "horizon_weeks": int(target["horizon_weeks"]),
        "sample_count": sample_count,
        "hit_rate": _mean_or_none(signed_target > 0) if sample_count else None,
        "average_forward_return": _mean_or_none(target_values[active]) if sample_count else None,
        "median_forward_return": _median_or_none(target_values[active]) if sample_count else None,
        "average_forward_drawdown": _mean_or_none(drawdown[active]) if drawdown is not None and sample_count else None,
        "information_coefficient": information_coefficient,
        "missing_data_ratio": round(missing_data_ratio, 4),
        "suggested_direction": suggested_direction,
        "suggested_weight_range": _suggested_weight_range(usable_for_score, information_coefficient),
        "usable_for_score": bool(usable_for_score),
    }
    return _clean_json(result)


def _oil_price_momentum_signal(frame: pd.DataFrame) -> pd.Series:
    existing = _first_existing(frame, ["oil_momentum_signal", "oil_price_momentum"])
    if existing is not None:
        return _mapped_text_signal(existing, _oil_momentum_score, frame.index)
    wti = _numeric_first_existing(frame, ["wti", "wti_close", "wti_price"])
    if wti is None:
        return pd.Series(np.nan, index=frame.index)
    momentum = wti.pct_change(13)
    return momentum.apply(lambda value: np.nan if pd.isna(value) else (1.0 if value > 0.05 else -1.0 if value < -0.05 else 0.0))


def _source_confidence_signal(frame: pd.DataFrame) -> pd.Series:
    source_columns = [
        "wti",
        "wti_curve_state",
        "curve_state",
        "oil_physical_tightness",
        "product_inventory_pressure",
        "macro_regime",
        "ten_year",
        "five_year_breakeven",
    ]
    available = [column for column in source_columns if column in frame.columns]
    if not available:
        return pd.Series(np.nan, index=frame.index)
    missing_ratio = frame[available].isna().mean(axis=1)
    return missing_ratio.apply(lambda value: 1.0 if value <= 0.25 else -1.0 if value >= 0.5 else 0.0)


def _first_existing(frame: pd.DataFrame, candidates: list[str]) -> pd.Series | None:
    for column in candidates:
        if column in frame.columns:
            return frame[column]
    return None


def _numeric_first_existing(frame: pd.DataFrame, candidates: list[str]) -> pd.Series | None:
    series = _first_existing(frame, candidates)
    if series is None:
        return None
    return pd.to_numeric(series, errors="coerce")


def _mapped_text_signal(series: pd.Series | None, mapper, index: pd.Index | None = None) -> pd.Series:
    if series is None:
        return pd.Series(np.nan, index=index, dtype=float)
    return series.apply(lambda value: mapper(_normalize_text(value)))


def _normalize_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return "MISSING"
    text = str(value).strip()
    if not text:
        return "MISSING"
    return text.upper().replace("-", "_").replace(" ", "_")


def _oil_momentum_score(value: str) -> float:
    if value == "MISSING" or "UNKNOWN" in value:
        return np.nan
    if "UP" in value or "STRENGTH" in value:
        return 1.0
    if "DOWN" in value or "WEAK" in value:
        return -1.0
    return 0.0


def _oil_regime_score(value: str) -> float:
    if value == "MISSING" or "UNKNOWN" in value:
        return np.nan
    if any(token in value for token in ["TIGHT", "STRENGTH", "SUPPLY_SHOCK", "INFLATION"]):
        return 1.0
    if any(token in value for token in ["BUILD", "WEAK", "RECESSION", "PRICE_WAR", "DOWN"]):
        return -1.0
    return 0.0


def _curve_state_score(value: str) -> float:
    if value in {"MISSING", "UNKNOWN"}:
        return np.nan
    if "BACKWARDATION" in value:
        return 1.0
    if "CONTANGO" in value:
        return -1.0
    return 0.0


def _physical_tightness_score(value: str) -> float:
    if value == "MISSING" or "UNKNOWN" in value:
        return np.nan
    if any(token in value for token in ["PHYSICAL_TIGHT", "EXPORT_LED_TIGHTNESS", "REFILL_SUPPORT", "TIGHT"]):
        return 1.0
    if "INVENTORY_BUILD" in value:
        return -1.0
    return 0.0


def _product_inventory_score(value: str) -> float:
    if value == "MISSING" or "UNKNOWN" in value:
        return np.nan
    if any(token in value for token in ["PRODUCT_TIGHTNESS", "CRUDE_DRAW_EXPORT_LED", "SPR_REFILL_SUPPORT", "TIGHT"]):
        return 1.0
    if "INVENTORY_BUILD" in value or "DEMAND_SOFTNESS" in value:
        return -1.0
    return 0.0


def _inflation_rates_score(value: str) -> float:
    if value == "MISSING" or "UNKNOWN" in value:
        return np.nan
    if any(token in value for token in ["INFLATION", "STAGFLATION", "RATES_UP", "BEAR", "POLICY_TIGHT"]):
        return 1.0
    if any(token in value for token in ["RECESSION", "DISINFLATION", "RATES_DOWN", "BULL", "CARRY_REPAIR"]):
        return -1.0
    return 0.0


def _forward_return(series: pd.Series, horizon: int) -> pd.Series:
    return series.shift(-horizon) / series - 1.0


def _forward_change(series: pd.Series, horizon: int) -> pd.Series:
    return series.shift(-horizon) - series


def _forward_drawdown(series: pd.Series, horizon: int) -> pd.Series:
    values = series.to_numpy(dtype=float)
    drawdowns = np.full(len(values), np.nan)
    for index, current in enumerate(values):
        end = index + horizon + 1
        if pd.isna(current) or end > len(values):
            continue
        future_window = values[index + 1 : end]
        if len(future_window) == 0 or np.isnan(future_window).all():
            continue
        drawdowns[index] = np.nanmin(future_window) / current - 1.0
    return pd.Series(drawdowns, index=series.index)


def _information_coefficient(signal: pd.Series, target: pd.Series, active: pd.Series) -> float | None:
    if int(active.sum()) < 3:
        return None
    signal_values = signal[active]
    target_values = target[active]
    if signal_values.nunique(dropna=True) < 2 or target_values.nunique(dropna=True) < 2:
        return None
    coefficient = signal_values.corr(target_values)
    if pd.isna(coefficient):
        return None
    return round(float(coefficient), 4)


def _suggested_direction(signed_target: pd.Series, insufficient: bool) -> str:
    if insufficient:
        return "INSUFFICIENT_DATA"
    aligned_average = signed_target.mean()
    if pd.isna(aligned_average):
        return "INSUFFICIENT_DATA"
    if aligned_average > 0:
        return "POSITIVE"
    if aligned_average < 0:
        return "NEGATIVE"
    return "NEUTRAL"


def _suggested_weight_range(usable_for_score: bool, information_coefficient: float | None) -> dict[str, float]:
    if not usable_for_score:
        return {"min": 0.0, "max": 0.0}
    strength = abs(information_coefficient or 0.0)
    if strength >= 0.15:
        return {"min": 0.05, "max": 0.15}
    return {"min": 0.0, "max": 0.05}


def _mean_or_none(values: pd.Series) -> float | None:
    if values.empty:
        return None
    value = values.mean()
    if pd.isna(value):
        return None
    return round(float(value), 6)


def _median_or_none(values: pd.Series) -> float | None:
    if values.empty:
        return None
    value = values.median()
    if pd.isna(value):
        return None
    return round(float(value), 6)


def _date_range(frame: pd.DataFrame) -> dict[str, str | None]:
    if "date" not in frame.columns or frame["date"].dropna().empty:
        return {"start": None, "end": None}
    dates = pd.to_datetime(frame["date"], errors="coerce").dropna()
    return {"start": str(dates.min().date()), "end": str(dates.max().date())}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_clean_json(payload), indent=2, ensure_ascii=False), encoding="utf-8")


def _clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _clean_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clean_json(item) for item in value]
    if isinstance(value, tuple):
        return [_clean_json(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        if pd.isna(value):
            return None
        return float(value)
    if value is pd.NA or value is pd.NaT:
        return None
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Run oil signal research backtest.")
    parser.add_argument("--input-path", default=str(DEFAULT_INPUT_PATH))
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--horizons-weeks", nargs="+", type=int, default=DEFAULT_HORIZONS_WEEKS)
    parser.add_argument("--min-samples", type=int, default=DEFAULT_MIN_SAMPLES)
    args = parser.parse_args()

    summary = run_oil_signal_backtest(
        input_path=args.input_path,
        output_path=args.output_path,
        horizons_weeks=args.horizons_weeks,
        min_samples=args.min_samples,
    )
    print(f"input_status={summary['input_status']}")
    print(f"results={len(summary['results'])}")
    print(f"output_path={args.output_path}")


if __name__ == "__main__":
    main()
