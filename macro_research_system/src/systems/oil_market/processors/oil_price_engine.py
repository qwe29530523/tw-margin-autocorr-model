from __future__ import annotations

import math

import pandas as pd


def _latest_return(series: pd.Series, periods: int) -> float | None:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if len(clean) <= periods:
        return None
    base = clean.iloc[-periods - 1]
    latest = clean.iloc[-1]
    if base == 0 or pd.isna(base) or pd.isna(latest):
        return None
    return float(latest / base - 1)


def _num_or_none(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def oil_momentum_signal(wti_return_5d: float | None, wti_return_20d: float | None) -> str:
    if wti_return_5d is not None and wti_return_5d > 0.05:
        return "oil_up_short_term"
    if wti_return_5d is not None and wti_return_5d < -0.05:
        return "oil_down_short_term"
    if wti_return_20d is not None and wti_return_20d > 0.05:
        return "oil_up_medium_term"
    if wti_return_20d is not None and wti_return_20d < -0.05:
        return "oil_down_medium_term"
    return "neutral"


def build_oil_price_metrics(frame: pd.DataFrame) -> dict:
    if frame.empty:
        return {
            "oil_asof_date": None,
            "wti": None,
            "brent": None,
            "brent_wti_spread": None,
            "wti_return_5d": None,
            "wti_return_20d": None,
            "wti_return_60d": None,
            "brent_return_5d": None,
            "brent_return_20d": None,
            "brent_return_60d": None,
            "oil_momentum_signal": "neutral",
        }
    df = frame.sort_values("date").copy()
    latest = df.iloc[-1]
    wti = _num_or_none(latest.get("wti"))
    brent = _num_or_none(latest.get("brent"))
    wti_return_5d = _latest_return(df["wti"], 5)
    wti_return_20d = _latest_return(df["wti"], 20)
    result = {
        "oil_asof_date": pd.to_datetime(latest["date"]).date().isoformat(),
        "wti": wti,
        "brent": brent,
        "brent_wti_spread": None if wti is None or brent is None else float(brent - wti),
        "wti_return_5d": wti_return_5d,
        "wti_return_20d": wti_return_20d,
        "wti_return_60d": _latest_return(df["wti"], 60),
        "brent_return_5d": _latest_return(df["brent"], 5),
        "brent_return_20d": _latest_return(df["brent"], 20),
        "brent_return_60d": _latest_return(df["brent"], 60),
    }
    result["oil_momentum_signal"] = oil_momentum_signal(wti_return_5d, wti_return_20d)
    return result


def pct_text(value: float | None) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "missing"
    return f"{value * 100:.2f}%"
