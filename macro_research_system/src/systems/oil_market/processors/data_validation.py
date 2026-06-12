from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.common.io import ensure_dir


MOCK_BANNER = "MOCK DATA ONLY — NOT FOR MARKET INTERPRETATION"


def _date_index_ok(frame: pd.DataFrame, expected: str) -> tuple[bool, str | None]:
    if "date" not in frame or frame.empty:
        return False, "missing date index"
    dates = pd.to_datetime(frame["date"], errors="coerce").dropna().sort_values()
    if len(dates) < 20:
        return False, "too few dated observations"
    if dates.duplicated().any():
        return False, "duplicated dates"
    gaps = dates.diff().dt.days.dropna()
    if expected == "daily" and gaps.median() > 5:
        return False, "daily series date frequency is not plausible"
    if expected == "weekly" and not (5 <= gaps.median() <= 10):
        return False, "weekly series date frequency is not plausible"
    return True, None


def _is_linear_ramp(series: pd.Series) -> bool:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if len(clean) < 20:
        return False
    diffs = clean.diff().dropna().round(8)
    if diffs.empty:
        return False
    return bool(diffs.nunique() <= 2 and abs(float(diffs.std())) < 1e-8)


def _is_repeating_pattern(series: pd.Series, max_period: int = 90, tolerance: float = 1e-9) -> bool:
    clean = pd.to_numeric(series, errors="coerce").dropna().to_numpy()
    period_limit = min(max_period, len(clean) // 3)
    if period_limit < 2:
        return False
    for period in range(2, period_limit + 1):
        head = clean[:-period]
        tail = clean[period:]
        if len(head) < period * 2:
            continue
        if np.nanmean(np.abs(head - tail)) <= tolerance:
            return True
    return False


def _is_detrended_repeating_pattern(series: pd.Series) -> bool:
    clean = pd.to_numeric(series, errors="coerce").dropna().to_numpy(dtype=float)
    if len(clean) < 80:
        return False
    x = np.arange(len(clean), dtype=float)
    slope, intercept = np.polyfit(x, clean, 1)
    residual = clean - (slope * x + intercept)
    return _is_repeating_pattern(pd.Series(np.round(residual, 6)), tolerance=1e-6)


def _is_sawtooth_like(series: pd.Series) -> bool:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if len(clean) < 80:
        return False
    diffs = clean.diff().dropna()
    abs_median = float(diffs.abs().median())
    if abs_median == 0 or np.isnan(abs_median):
        return False
    positive_ratio = float((diffs > 0).mean())
    reset_count = int((diffs < -(abs_median * 5)).sum())
    return positive_ratio >= 0.70 and reset_count >= 2


def _series_warnings(frame: pd.DataFrame, columns: list[str], label: str) -> list[str]:
    warnings: list[str] = []
    for column in columns:
        if column not in frame:
            warnings.append(f"{label} missing required column: {column}")
            continue
        if _is_linear_ramp(frame[column]):
            warnings.append(f"{label} {column} looks like monotonic linear ramp fixture data.")
        if (
            _is_repeating_pattern(frame[column])
            or _is_detrended_repeating_pattern(frame[column])
            or _is_sawtooth_like(frame[column])
        ):
            warnings.append(f"{label} {column} looks like repeating sawtooth or fixed periodic fixture data.")
        values = pd.to_numeric(frame[column], errors="coerce").dropna()
        if values.nunique() <= 2 and len(values) >= 20:
            warnings.append(f"{label} {column} looks like repeating square wave fixture data.")
    return warnings


def _inventory_change_warnings(frame: pd.DataFrame) -> list[str]:
    warnings: list[str] = []
    for column in ["crude_inventory", "gasoline_inventory", "distillate_inventory"]:
        if column not in frame:
            continue
        change = pd.to_numeric(frame[column], errors="coerce").diff(4).dropna()
        if _is_repeating_pattern(change) or _is_detrended_repeating_pattern(change):
            warnings.append(f"EIA {column} 4W change looks like fixed periodic fixture data.")
    return warnings


def _crack_spread_warnings(frame: pd.DataFrame) -> list[str]:
    warnings: list[str] = []
    for column in ["gasoline_crack_proxy", "diesel_crack_proxy"]:
        if column not in frame:
            warnings.append(f"EIA missing required column: {column}")
            continue
        if _is_linear_ramp(frame[column]):
            warnings.append(f"EIA crack spread {column} looks like linear ramp fixture data.")
        if _is_repeating_pattern(frame[column]) or _is_detrended_repeating_pattern(frame[column]):
            warnings.append(f"EIA crack spread {column} looks like fixed periodic fixture data.")
    return warnings


def validate_fred_frame(frame: pd.DataFrame, source_mode: str) -> dict:
    warnings: list[str] = []
    ok, date_warning = _date_index_ok(frame, "daily")
    if date_warning:
        warnings.append(f"FRED {date_warning}.")
    warnings.extend(_series_warnings(frame, ["wti", "brent"], "FRED"))
    if source_mode != "real":
        warnings.append("FRED source mode is not real API data.")
    real_data = source_mode == "real" and ok and not warnings
    return {"source": "fred", "real_data": real_data, "warnings": warnings}


def validate_eia_frame(frame: pd.DataFrame, source_mode: str) -> dict:
    warnings: list[str] = []
    ok, date_warning = _date_index_ok(frame, "weekly")
    if date_warning:
        warnings.append(f"EIA {date_warning}.")
    columns = [
        "crude_inventory",
        "gasoline_inventory",
        "distillate_inventory",
        "refinery_utilization",
        "refinery_crude_inputs",
        "gasoline_product_supplied",
        "distillate_product_supplied",
        "jet_fuel_product_supplied",
        "crude_production",
        "crude_exports",
    ]
    warnings.extend(_series_warnings(frame, columns, "EIA"))
    warnings.extend(_inventory_change_warnings(frame))
    warnings.extend(_crack_spread_warnings(frame))
    if source_mode != "real":
        warnings.append("EIA source mode is not real API data.")
    real_data = source_mode == "real" and ok and not warnings
    return {"source": "eia", "real_data": real_data, "warnings": warnings}


def write_data_validation_log(output_dir: Path, fred_validation: dict, eia_validation: dict) -> Path:
    ensure_dir(output_dir)
    path = output_dir / "data_validation_log.txt"
    fred_warnings = fred_validation.get("warnings", [])
    eia_warnings = eia_validation.get("warnings", [])
    validation_passed = bool(fred_validation["real_data"] and eia_validation["real_data"] and not fred_warnings and not eia_warnings)
    lines = [
        "Oil market data validation log",
        f"Data validation passed: {validation_passed}",
        f"FRED real data: {fred_validation['real_data']}",
        "FRED warnings: none" if not fred_warnings else "FRED warnings:",
        *[f"FRED warning: {item}" for item in fred_warnings],
        f"EIA real data: {eia_validation['real_data']}",
        "EIA warnings: none" if not eia_warnings else "EIA warnings:",
        *[f"EIA warning: {item}" for item in eia_warnings],
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
