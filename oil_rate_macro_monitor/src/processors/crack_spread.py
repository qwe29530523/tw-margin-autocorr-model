from __future__ import annotations

import numpy as np
import pandas as pd

from src.processors.oil_curve import price_pivot


CRACK_SPREAD_COLUMNS = [
    "date",
    "gasoline_crack",
    "diesel_crack",
    "gasoline_crack_20d_change",
    "diesel_crack_20d_change",
    "gasoline_crack_20d_ma",
    "diesel_crack_20d_ma",
    "crack_signal",
]


def calculate_crack_spreads(prices: pd.DataFrame) -> pd.DataFrame:
    wide = price_pivot(prices)
    if wide.empty:
        return pd.DataFrame(columns=CRACK_SPREAD_COLUMNS)
    wide["date"] = pd.to_datetime(wide["date"], errors="coerce")
    wide = wide.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in ["wti", "rb", "ho"]:
        if column not in wide.columns:
            wide[column] = np.nan
        wide[column] = pd.to_numeric(wide[column], errors="coerce")

    out = wide[["date"]].copy()
    out["gasoline_crack"] = (wide["rb"] * 42 - wide["wti"]).round(6)
    out["diesel_crack"] = (wide["ho"] * 42 - wide["wti"]).round(6)
    gasoline_ma = out["gasoline_crack"].rolling(20, min_periods=1).mean()
    diesel_ma = out["diesel_crack"].rolling(20, min_periods=1).mean()
    out["gasoline_crack_20d_change"] = out["gasoline_crack"].diff(20)
    out["diesel_crack_20d_change"] = out["diesel_crack"].diff(20)
    out["gasoline_crack_20d_ma"] = gasoline_ma
    out["diesel_crack_20d_ma"] = diesel_ma
    gasoline_rising = gasoline_ma.diff() > 0
    diesel_rising = diesel_ma.diff() > 0
    gasoline_falling = gasoline_ma.diff() < 0
    diesel_falling = diesel_ma.diff() < 0

    out["crack_signal"] = "mixed"
    out.loc[
        (out["diesel_crack"] > out["gasoline_crack"]) & diesel_rising,
        "crack_signal",
    ] = "industrial_logistics_strength"
    out.loc[
        (out["gasoline_crack"] > out["diesel_crack"]) & gasoline_rising,
        "crack_signal",
    ] = "driving_season_strength"
    out.loc[gasoline_falling & diesel_falling, "crack_signal"] = "demand_weakening"
    return out[CRACK_SPREAD_COLUMNS]
