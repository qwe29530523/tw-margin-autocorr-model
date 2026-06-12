from __future__ import annotations

import pandas as pd

from src.systems.oil_market.processors.inventory_engine import _change_4w


def _latest(df: pd.DataFrame, column: str) -> float | None:
    if column not in df or df.empty:
        return None
    clean = pd.to_numeric(df[column], errors="coerce").dropna()
    if clean.empty:
        return None
    return float(clean.iloc[-1])


def build_supply_metrics(frame: pd.DataFrame, inventory_signal: str = "neutral") -> dict:
    df = frame.sort_values("date").copy()
    production = _latest(df, "crude_production")
    exports = _latest(df, "crude_exports")
    production_change = _change_4w(df, "crude_production")
    exports_change = _change_4w(df, "crude_exports")
    exports_series = pd.to_numeric(df.get("crude_exports", pd.Series(dtype=float)), errors="coerce").dropna()
    export_high = exports is not None and not exports_series.empty and exports >= float(exports_series.quantile(0.80))
    if production_change is not None and exports_change is not None and production_change > 0 and exports_change > 0:
        signal = "us_supply_expanding_export_pressure"
    elif (production_change is None or production_change <= 0) and inventory_signal == "inventory_tightening":
        signal = "us_supply_tight"
    elif export_high:
        signal = "export_pressure_high"
    else:
        signal = "neutral"
    return {
        "crude_production": production,
        "crude_exports": exports,
        "crude_production_4w_change": production_change,
        "crude_exports_4w_change": exports_change,
        "supply_signal": signal,
    }
