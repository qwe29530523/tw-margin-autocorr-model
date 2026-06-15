from __future__ import annotations

import numpy as np
import pandas as pd


RATE_SERIES_MAP = {
    "FEDFUNDS": "fedfunds",
    "SOFR": "sofr",
    "DGS3MO": "three_month",
    "DGS1": "one_year",
    "DGS2": "two_year",
    "DGS5": "five_year",
    "DGS10": "ten_year",
    "DGS30": "thirty_year",
    "T10Y2Y": "ten_year_two_year_spread_fred",
    "T10Y3M": "ten_year_three_month_spread_fred",
    "T5YIE": "breakeven_5y",
    "T10YIE": "breakeven_10y",
}

CURVE_TENORS = ["three_month", "two_year", "five_year", "ten_year", "thirty_year"]


def build_rates_curve_frame(fred_data: pd.DataFrame) -> pd.DataFrame:
    if fred_data.empty:
        return pd.DataFrame()
    df = fred_data[fred_data["series_id"].isin(RATE_SERIES_MAP)].copy()
    if df.empty:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    pivot = df.pivot_table(index="date", columns="series_id", values="value", aggfunc="last").reset_index()
    pivot = pivot.rename(columns=RATE_SERIES_MAP).sort_values("date").reset_index(drop=True)
    for column in RATE_SERIES_MAP.values():
        if column not in pivot.columns:
            pivot[column] = np.nan
    raw_pivot = pivot.copy()

    complete_curve_date = raw_pivot[CURVE_TENORS].notna().all(axis=1)
    pivot["rates_curve_asof_date"] = pd.Series(pd.NaT, index=pivot.index, dtype="datetime64[ns]")
    pivot.loc[complete_curve_date, "rates_curve_asof_date"] = pivot.loc[complete_curve_date, "date"]
    pivot["rates_curve_asof_date"] = pivot["rates_curve_asof_date"].ffill()

    for column in CURVE_TENORS:
        pivot[column] = raw_pivot[column].where(complete_curve_date).ffill()
        pivot[f"{column}_asof_date"] = pivot["rates_curve_asof_date"]
    for column in set(RATE_SERIES_MAP.values()) - set(CURVE_TENORS):
        pivot[f"{column}_asof_date"] = _asof_dates(pivot["date"], pivot[column])
        pivot[column] = pivot[column].ffill()

    out = pivot.copy()
    for column in ["two_year", "five_year", "ten_year", "thirty_year"]:
        for window in [5, 20, 60]:
            out[f"{column}_change_{window}d"] = out[column].diff(window)

    out["ten_year_three_month_spread"] = out["ten_year"] - out["three_month"]
    out["ten_year_two_year_spread"] = out["ten_year"] - out["two_year"]
    out["five_year_two_year_spread"] = out["five_year"] - out["two_year"]
    out["ten_year_five_year_spread"] = out["ten_year"] - out["five_year"]
    out["thirty_year_ten_year_spread"] = out["thirty_year"] - out["ten_year"]
    out["ten_year_two_year_spread_change_20d"] = out["ten_year_two_year_spread"].diff(20)
    out["ten_year_three_month_spread_change_20d"] = out["ten_year_three_month_spread"].diff(20)
    out["ten_year_two_year_spread_asof_date"] = out["rates_curve_asof_date"]
    out["ten_year_three_month_spread_asof_date"] = out["rates_curve_asof_date"]
    out["five_year_two_year_spread_asof_date"] = out["rates_curve_asof_date"]
    out["ten_year_five_year_spread_asof_date"] = out["rates_curve_asof_date"]
    out["thirty_year_ten_year_spread_asof_date"] = out["rates_curve_asof_date"]
    out["belly_relative_move"] = (
        out["five_year_change_20d"].abs()
        - pd.concat([out["two_year_change_20d"].abs(), out["ten_year_change_20d"].abs()], axis=1).mean(axis=1)
    )

    for tenor in ["two_year", "five_year", "ten_year", "thirty_year"]:
        out[f"{tenor}_sofr_carry_proxy"] = out[tenor] - out["sofr"]
        out[f"{tenor}_sofr_carry_change_20d"] = out[f"{tenor}_sofr_carry_proxy"].diff(20)

    out["sofr_fedfunds_spread"] = out["sofr"] - out["fedfunds"]
    out["three_month_fedfunds_spread"] = out["three_month"] - out["fedfunds"]
    out["funding_pressure_signal"] = out.apply(_funding_pressure_signal, axis=1)
    out["curve_slope_state"] = out.apply(_curve_slope_state, axis=1)
    out["belly_signal"] = out.apply(_belly_signal, axis=1)
    out["carry_signal"] = out.apply(_carry_signal, axis=1)
    out["roll_down_signal"] = out.apply(_roll_down_signal, axis=1)
    out["long_end_anchor_signal"] = out.apply(_long_end_anchor_signal, axis=1)
    out["policy_rate_level"] = out.apply(_policy_rate_level, axis=1)
    out["rates_regime"] = out.apply(_rates_regime, axis=1)
    out["fred_rates_asof_date"] = _max_datetime_columns(
        out,
        [
            "fedfunds_asof_date",
            "sofr_asof_date",
            "three_month_asof_date",
            "one_year_asof_date",
            "two_year_asof_date",
            "five_year_asof_date",
            "ten_year_asof_date",
            "thirty_year_asof_date",
        ],
    )
    return out


def _funding_pressure_signal(row: pd.Series) -> str:
    sofr_spread = row.get("sofr_fedfunds_spread", np.nan)
    three_month_spread = row.get("three_month_fedfunds_spread", np.nan)
    if pd.isna(sofr_spread) and pd.isna(three_month_spread):
        return "funding_pressure_unknown"
    if _gte(sofr_spread, 0.30) or _gte(three_month_spread, 0.50):
        return "funding_pressure_stress"
    if _gte(sofr_spread, 0.15) or _gte(three_month_spread, 0.35):
        return "funding_pressure_elevated"
    if _gte(sofr_spread, 0.05) or _gte(three_month_spread, 0.20):
        return "funding_pressure_mild"
    return "funding_pressure_low"


def _curve_slope_state(row: pd.Series) -> str:
    if row.get("ten_year_three_month_spread", np.nan) < 0 or row.get("ten_year_two_year_spread", np.nan) < 0:
        return "inversion_pressure"
    if row.get("ten_year_two_year_spread", np.nan) > 0.5:
        return "steep"
    if row.get("ten_year_two_year_spread", np.nan) > 0:
        return "positive_slope"
    return "mixed"


def _belly_signal(row: pd.Series) -> str:
    five = abs(row.get("five_year_change_20d", np.nan))
    two = abs(row.get("two_year_change_20d", np.nan))
    ten = abs(row.get("ten_year_change_20d", np.nan))
    if pd.isna(five) or pd.isna(two) or pd.isna(ten):
        return "belly_normal"
    wing_average = pd.Series([two, ten]).mean()
    relative_move = five - wing_average
    if relative_move > 0.05 and five >= max(wing_average * 1.5, wing_average + 0.05):
        return "belly_stress"
    return "belly_normal"


def _carry_signal(row: pd.Series) -> str:
    carry = row.get("ten_year_sofr_carry_proxy", np.nan)
    carry_change = row.get("ten_year_sofr_carry_change_20d", np.nan)
    if pd.notna(carry_change) and carry_change > 0:
        return "carry_repair"
    if pd.notna(carry_change) and carry_change < 0:
        return "carry_deterioration"
    if pd.notna(carry) and carry > 0:
        return "positive_carry"
    if pd.notna(carry) and carry < 0:
        return "negative_carry"
    return "mixed"


def _roll_down_signal(row: pd.Series) -> str:
    five_two = row.get("five_year_two_year_spread", np.nan)
    ten_five = row.get("ten_year_five_year_spread", np.nan)
    if (pd.notna(five_two) and five_two > 0) or (pd.notna(ten_five) and ten_five > 0):
        return "roll_down_supportive"
    if pd.notna(five_two) and pd.notna(ten_five) and five_two < 0 and ten_five < 0:
        return "roll_down_unattractive"
    return "mixed"


def _long_end_anchor_signal(row: pd.Series) -> str:
    thirty = abs(row.get("thirty_year_change_20d", np.nan))
    five = abs(row.get("five_year_change_20d", np.nan))
    if pd.notna(thirty) and pd.notna(five) and thirty < five:
        return "anchored_long_end"
    return "mixed"


def _policy_rate_level(row: pd.Series) -> str:
    if row.get("fedfunds", np.nan) >= 4.0 and row.get("sofr", np.nan) >= 4.0:
        return "policy_tight"
    return "mixed"


def _rates_regime(row: pd.Series) -> str:
    if row.get("curve_slope_state") == "inversion_pressure":
        return "inversion_pressure"
    if row.get("ten_year_sofr_carry_proxy", np.nan) < 0:
        return "negative_carry"
    if row.get("belly_signal") == "belly_stress":
        return "belly_stress"
    if row.get("two_year_change_20d", np.nan) < 0 and row.get("ten_year_two_year_spread_change_20d", np.nan) > 0:
        return "bull_steepening"
    if row.get("ten_year_change_20d", np.nan) > 0 and row.get("ten_year_two_year_spread_change_20d", np.nan) > 0:
        return "bear_steepening"
    if row.get("carry_signal") == "carry_repair":
        return "carry_repair"
    if row.get("long_end_anchor_signal") == "anchored_long_end":
        return "anchored_long_end"
    if row.get("policy_rate_level") == "policy_tight":
        return "policy_tight"
    return "mixed"


def _gte(value: float, threshold: float) -> bool:
    return pd.notna(value) and value >= threshold


def _asof_dates(dates: pd.Series, values: pd.Series) -> pd.Series:
    asof = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns]")
    valid = values.notna()
    asof.loc[valid] = pd.to_datetime(dates.loc[valid], errors="coerce")
    return asof.ffill()


def _max_datetime_columns(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    existing = [column for column in columns if column in df.columns]
    if not existing:
        return pd.Series(pd.NaT, index=df.index)
    return pd.concat([pd.to_datetime(df[column], errors="coerce") for column in existing], axis=1).max(axis=1)
