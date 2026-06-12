from __future__ import annotations

import pandas as pd


def _change(df: pd.DataFrame, column: str, periods: int) -> float | None:
    if column not in df:
        return None
    series = pd.to_numeric(df[column], errors="coerce").dropna()
    if len(series) <= periods:
        return None
    return float(series.iloc[-1] - series.iloc[-periods - 1])


def _latest(df: pd.DataFrame, column: str) -> float | None:
    if column not in df or df.empty:
        return None
    value = pd.to_numeric(df[column], errors="coerce").dropna()
    if value.empty:
        return None
    return float(value.iloc[-1])


def _latest_text(df: pd.DataFrame, column: str) -> str | None:
    if column not in df or df.empty:
        return None
    values = df[column].dropna()
    if values.empty:
        return None
    return str(values.iloc[-1])


def _is_high(series: pd.Series, value: float | None) -> bool:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if value is None or clean.empty:
        return False
    return value >= float(clean.quantile(0.80))


def crack_signal(
    gasoline_crack: float | None,
    diesel_crack: float | None,
    gasoline_change: float | None,
    diesel_change: float | None,
    elevated: bool,
    product_demand_signal: str,
) -> str:
    if product_demand_signal == "broad_product_demand_softening" and elevated:
        return "product_demand_softening_with_elevated_cracks"
    if elevated:
        return "elevated_cracks"
    if gasoline_change is not None and diesel_change is not None and gasoline_change > 0 and diesel_change > 0:
        return "crack_strengthening"
    if gasoline_change is not None and diesel_change is not None and gasoline_change < 0 and diesel_change < 0:
        return "crack_weakening"
    return "neutral"


def build_crack_spread_metrics(frame: pd.DataFrame, product_demand_signal: str = "neutral") -> dict:
    df = frame.sort_values("date").copy()
    gasoline = _latest(df, "gasoline_crack_proxy")
    diesel = _latest(df, "diesel_crack_proxy")
    gasoline_change = _change(df, "gasoline_crack_proxy", 20)
    diesel_change = _change(df, "diesel_crack_proxy", 20)
    elevated = _is_high(df.get("gasoline_crack_proxy", pd.Series(dtype=float)), gasoline) or _is_high(
        df.get("diesel_crack_proxy", pd.Series(dtype=float)), diesel
    )
    return {
        "gasoline_crack_proxy": gasoline,
        "diesel_crack_proxy": diesel,
        "gasoline_crack_20d_change": gasoline_change,
        "diesel_crack_20d_change": diesel_change,
        "crack_spread_asof_date": _latest_text(df, "crack_spread_asof_date"),
        "crack_signal": crack_signal(gasoline, diesel, gasoline_change, diesel_change, elevated, product_demand_signal),
    }
