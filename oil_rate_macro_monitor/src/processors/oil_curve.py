from __future__ import annotations

import numpy as np
import pandas as pd


OIL_CURVE_COLUMNS = [
    "date",
    "wti",
    "brent",
    "wti_daily_return",
    "brent_daily_return",
    "brent_wti_spread",
    "wti_return_5d",
    "brent_return_5d",
    "wti_return_20d",
    "brent_return_20d",
    "wti_return_60d",
    "brent_return_60d",
    "m1_m2_spread",
    "m1_m3_spread",
    "curve_state",
]


def price_pivot(prices: pd.DataFrame) -> pd.DataFrame:
    if prices.empty:
        return pd.DataFrame(columns=["date"])
    if {"date", "ticker", "close"}.issubset(prices.columns):
        wide = prices.pivot_table(index="date", columns="ticker", values="close", aggfunc="last").reset_index()
        return wide.rename(columns={"CL=F": "wti", "BZ=F": "brent", "RB=F": "rb", "HO=F": "ho"})
    return prices.copy()


def calculate_oil_curve(prices: pd.DataFrame) -> pd.DataFrame:
    wide = price_pivot(prices)
    if wide.empty:
        return pd.DataFrame(columns=OIL_CURVE_COLUMNS)
    wide["date"] = pd.to_datetime(wide["date"], errors="coerce")
    wide = wide.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in ["wti", "brent"]:
        if column not in wide.columns:
            wide[column] = np.nan
        wide[column] = pd.to_numeric(wide[column], errors="coerce")

    out = wide[["date", "wti", "brent"]].copy()
    out["wti_daily_return"] = out["wti"].pct_change()
    out["brent_daily_return"] = out["brent"].pct_change()
    out["brent_wti_spread"] = out["brent"] - out["wti"]
    for window in [5, 20, 60]:
        out[f"wti_return_{window}d"] = out["wti"].pct_change(window)
        out[f"brent_return_{window}d"] = out["brent"].pct_change(window)

    if {"m1", "m2"}.issubset(wide.columns):
        out["m1_m2_spread"] = pd.to_numeric(wide["m1"], errors="coerce") - pd.to_numeric(wide["m2"], errors="coerce")
        if "m3" in wide.columns:
            out["m1_m3_spread"] = pd.to_numeric(wide["m1"], errors="coerce") - pd.to_numeric(wide["m3"], errors="coerce")
        else:
            out["m1_m3_spread"] = np.nan
        out["curve_state"] = np.select(
            [out["m1_m2_spread"].abs() < 0.1, out["m1_m2_spread"] > 0, out["m1_m2_spread"] < 0],
            ["flat", "backwardation", "contango"],
            default="unknown",
        )
    else:
        out["m1_m2_spread"] = np.nan
        out["m1_m3_spread"] = np.nan
        out["curve_state"] = "unknown"
    return out
