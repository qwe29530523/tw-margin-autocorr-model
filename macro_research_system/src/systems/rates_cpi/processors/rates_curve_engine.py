from __future__ import annotations

import pandas as pd


SERIES_MAP = {
    "FEDFUNDS": "fed_funds",
    "SOFR": "sofr",
    "DGS3MO": "rate_3m",
    "DGS1": "rate_1y",
    "DGS2": "rate_2y",
    "DGS5": "rate_5y",
    "DGS10": "rate_10y",
    "DGS30": "rate_30y",
    "T10Y2Y": "spread_10y_2y_fred",
    "T10Y3M": "spread_10y_3m_fred",
}

CURVE_COLUMNS = ["rate_3m", "rate_1y", "rate_2y", "rate_5y", "rate_10y", "rate_30y"]


def _num(value) -> float | None:
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        return None
    return round(float(value), 6)


def funding_pressure_signal(sofr_spread: float | None, three_month_spread: float | None) -> str:
    sofr_spread = sofr_spread or 0.0
    three_month_spread = three_month_spread or 0.0
    if sofr_spread >= 0.30 or three_month_spread >= 0.50:
        return "funding_pressure_stress"
    if sofr_spread >= 0.15 or three_month_spread >= 0.35:
        return "funding_pressure_elevated"
    if sofr_spread >= 0.05 or three_month_spread >= 0.20:
        return "funding_pressure_mild"
    return "funding_pressure_low"


def curve_signal(spread_10y_3m: float | None, spread_10y_2y: float | None) -> str:
    if spread_10y_3m is None or spread_10y_2y is None:
        return "unknown"
    if spread_10y_3m < 0 and spread_10y_2y < 0:
        return "deep_inversion"
    if spread_10y_3m < 0 or spread_10y_2y < 0:
        return "partial_inversion"
    if spread_10y_3m > 1.0 and spread_10y_2y > 0.5:
        return "steepening"
    return "neutral"


def carry_signal(rate_10y: float | None, sofr: float | None) -> str:
    if rate_10y is None or sofr is None:
        return "unknown"
    return "carry_positive" if rate_10y > sofr else "carry_negative"


def rates_regime(curve: str, funding: str) -> str:
    if funding in {"funding_pressure_elevated", "funding_pressure_stress"}:
        return "funding_pressure"
    if curve in {"deep_inversion", "partial_inversion"}:
        return "curve_inversion"
    if curve == "steepening":
        return "curve_steepening"
    return "neutral"


def build_rates_metrics(frame: pd.DataFrame) -> dict:
    if frame.empty:
        return {
            "rates_asof_date": None,
            "rates_regime": "unknown",
            "funding_pressure_signal": "unknown",
            "carry_signal": "unknown",
            "curve_signal": "unknown",
        }
    df = frame.copy()
    df["date"] = pd.to_datetime(df["date"])
    pivot = df.pivot_table(index="date", columns="series", values="value", aggfunc="last").rename(columns=SERIES_MAP)
    for column in SERIES_MAP.values():
        if column not in pivot:
            pivot[column] = pd.NA
    curve_complete = pivot.dropna(subset=CURVE_COLUMNS)
    if curve_complete.empty:
        return {
            "rates_asof_date": None,
            "rates_regime": "unknown",
            "funding_pressure_signal": "unknown",
            "carry_signal": "unknown",
            "curve_signal": "unknown",
        }
    rates_asof = curve_complete.index.max()
    latest = curve_complete.loc[rates_asof].to_dict()
    official = pivot.ffill().iloc[-1].to_dict()
    fed_funds = _num(official.get("fed_funds"))
    sofr = _num(official.get("sofr"))
    rate_3m = _num(latest.get("rate_3m"))
    rate_1y = _num(latest.get("rate_1y"))
    rate_2y = _num(latest.get("rate_2y"))
    rate_5y = _num(latest.get("rate_5y"))
    rate_10y = _num(latest.get("rate_10y"))
    rate_30y = _num(latest.get("rate_30y"))
    spread_10y_3m = None if rate_10y is None or rate_3m is None else round(rate_10y - rate_3m, 6)
    spread_10y_2y = None if rate_10y is None or rate_2y is None else round(rate_10y - rate_2y, 6)
    spread_5y_2y = None if rate_5y is None or rate_2y is None else round(rate_5y - rate_2y, 6)
    spread_30y_10y = None if rate_30y is None or rate_10y is None else round(rate_30y - rate_10y, 6)
    sofr_fed = None if sofr is None or fed_funds is None else round(sofr - fed_funds, 6)
    three_month_fed = None if rate_3m is None or fed_funds is None else round(rate_3m - fed_funds, 6)
    funding = funding_pressure_signal(sofr_fed, three_month_fed)
    curve = curve_signal(spread_10y_3m, spread_10y_2y)
    carry = carry_signal(rate_10y, sofr)
    return {
        "rates_asof_date": rates_asof.date().isoformat(),
        "rates_regime": rates_regime(curve, funding),
        "funding_pressure_signal": funding,
        "carry_signal": carry,
        "curve_signal": curve,
        "fed_funds": fed_funds,
        "sofr": sofr,
        "rate_3m": rate_3m,
        "rate_1y": rate_1y,
        "rate_2y": rate_2y,
        "rate_5y": rate_5y,
        "rate_10y": rate_10y,
        "rate_30y": rate_30y,
        "spread_10y_3m": spread_10y_3m,
        "spread_10y_2y": spread_10y_2y,
        "spread_5y_2y": spread_5y_2y,
        "spread_30y_10y": spread_30y_10y,
        "sofr_fed_funds_spread": sofr_fed,
        "three_month_fed_funds_spread": three_month_fed,
    }
