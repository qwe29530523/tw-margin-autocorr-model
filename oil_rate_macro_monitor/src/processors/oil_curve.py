from __future__ import annotations

import numpy as np
import pandas as pd


WTI_CURVE_FLAT_THRESHOLD = 0.10

OIL_CURVE_COLUMNS = [
    "date",
    "wti",
    "brent",
    "cl_m1_settle",
    "cl_m2_settle",
    "cl_m3_settle",
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
    "source",
    "source_type",
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
    for column in ["cl_m1_settle", "cl_m2_settle", "cl_m3_settle"]:
        if column not in wide.columns:
            wide[column] = np.nan
        wide[column] = pd.to_numeric(wide[column], errors="coerce")
        out[column] = wide[column]
    out["wti_daily_return"] = out["wti"].pct_change()
    out["brent_daily_return"] = out["brent"].pct_change()
    out["brent_wti_spread"] = out["brent"] - out["wti"]
    for window in [5, 20, 60]:
        out[f"wti_return_{window}d"] = out["wti"].pct_change(window)
        out[f"brent_return_{window}d"] = out["brent"].pct_change(window)

    if {"m1", "m2", "m3"}.issubset(wide.columns) and out["cl_m1_settle"].isna().all():
        out["cl_m1_settle"] = pd.to_numeric(wide["m1"], errors="coerce")
        out["cl_m2_settle"] = pd.to_numeric(wide["m2"], errors="coerce")
        out["cl_m3_settle"] = pd.to_numeric(wide["m3"], errors="coerce")

    valid_curve = out[["cl_m1_settle", "cl_m2_settle", "cl_m3_settle"]].notna().all(axis=1)
    out["m1_m2_spread"] = np.where(
        valid_curve,
        out["cl_m1_settle"] - out["cl_m2_settle"],
        np.nan,
    )
    out["m1_m3_spread"] = np.where(
        valid_curve,
        out["cl_m1_settle"] - out["cl_m3_settle"],
        np.nan,
    )
    out["curve_state"] = np.select(
        [
            ~valid_curve,
            out["m1_m2_spread"] > WTI_CURVE_FLAT_THRESHOLD,
            out["m1_m2_spread"] < -WTI_CURVE_FLAT_THRESHOLD,
        ],
        ["unknown", "backwardation", "contango"],
        default="flat",
    )
    for column in ["source", "source_type"]:
        out[column] = wide[column] if column in wide.columns else pd.NA
    return out


def combine_oil_prices_with_wti_curve(oil_prices: pd.DataFrame, wti_curve: pd.DataFrame) -> pd.DataFrame:
    price_columns = [column for column in ["date", "wti", "brent"] if column in oil_prices.columns]
    prices = oil_prices[price_columns].copy() if price_columns else pd.DataFrame(columns=["date"])
    if wti_curve.empty:
        return prices
    curve_columns = [
        column
        for column in ["date", "cl_m1_settle", "cl_m2_settle", "cl_m3_settle", "source", "source_type"]
        if column in wti_curve.columns
    ]
    curve = wti_curve[curve_columns].copy()
    if prices.empty:
        return curve
    return pd.merge(prices, curve, on="date", how="outer").sort_values("date").reset_index(drop=True)
