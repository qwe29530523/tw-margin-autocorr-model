from __future__ import annotations

import pandas as pd


SERIES_MAP = {
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
}
CURVE = ["three_month", "two_year", "five_year", "ten_year", "thirty_year"]


def _output_value(value):
    try:
        if pd.isna(value):
            return "missing"
    except (TypeError, ValueError):
        pass
    return value


def funding_pressure_signal(sofr_spread: float, three_month_spread: float) -> str:
    if sofr_spread >= 0.30 or three_month_spread >= 0.50:
        return "funding_pressure_stress"
    if sofr_spread >= 0.15 or three_month_spread >= 0.35:
        return "funding_pressure_elevated"
    if sofr_spread >= 0.05 or three_month_spread >= 0.20:
        return "funding_pressure_mild"
    return "funding_pressure_low"


def build_rates_curve_metrics(frame: pd.DataFrame) -> dict:
    df = frame.copy()
    df["date"] = pd.to_datetime(df["date"])
    pivot = df.pivot_table(index="date", columns="series", values="value", aggfunc="last").rename(columns=SERIES_MAP)
    for column in SERIES_MAP.values():
        if column not in pivot:
            pivot[column] = pd.NA
    complete = pivot.dropna(subset=CURVE)
    curve_asof = complete.index.max()
    latest = complete.loc[curve_asof].to_dict()
    previous = complete.iloc[-21].to_dict() if len(complete) > 20 else complete.iloc[0].to_dict()
    official = pivot.ffill().iloc[-1].to_dict()
    fedfunds = float(official.get("fedfunds", latest.get("fedfunds", 0)) or 0)
    sofr = float(official.get("sofr", latest.get("sofr", 0)) or 0)
    three_month = float(latest["three_month"])
    two_year = float(latest["two_year"])
    five_year = float(latest["five_year"])
    ten_year = float(latest["ten_year"])
    thirty_year = float(latest["thirty_year"])
    ten_sofr = round(ten_year - sofr, 4)
    previous_ten_sofr = round(float(previous.get("ten_year", ten_year)) - float(previous.get("sofr", sofr) or sofr), 4)
    carry_signal = "carry_repair" if ten_sofr > previous_ten_sofr else "neutral"
    two_change = round(two_year - float(previous.get("two_year", two_year)), 4)
    five_change = round(five_year - float(previous.get("five_year", five_year)), 4)
    ten_change = round(ten_year - float(previous.get("ten_year", ten_year)), 4)
    thirty_change = round(thirty_year - float(previous.get("thirty_year", thirty_year)), 4)
    belly_relative_move = round(abs(five_change) - ((abs(two_change) + abs(ten_change)) / 2), 4)
    return {
        "rates_asof_date": curve_asof.date().isoformat(),
        "rates_curve_asof_date": curve_asof.date().isoformat(),
        "fedfunds": fedfunds,
        "sofr": sofr,
        "three_month": three_month,
        "one_year": _output_value(official.get("one_year")),
        "two_year": two_year,
        "five_year": five_year,
        "ten_year": ten_year,
        "thirty_year": thirty_year,
        "ten_year_three_month_spread": round(ten_year - three_month, 4),
        "ten_year_two_year_spread": round(ten_year - two_year, 4),
        "five_year_two_year_spread": round(five_year - two_year, 4),
        "ten_year_five_year_spread": round(ten_year - five_year, 4),
        "thirty_year_ten_year_spread": round(thirty_year - ten_year, 4),
        "ten_year_two_year_spread_fred": _output_value(official.get("ten_year_two_year_spread_fred")),
        "ten_year_three_month_spread_fred": _output_value(official.get("ten_year_three_month_spread_fred")),
        "two_year_sofr_carry_proxy": round(two_year - sofr, 4),
        "five_year_sofr_carry_proxy": round(five_year - sofr, 4),
        "ten_year_sofr_carry_proxy": ten_sofr,
        "thirty_year_sofr_carry_proxy": round(thirty_year - sofr, 4),
        "sofr_fedfunds_spread": round(sofr - fedfunds, 4),
        "three_month_fedfunds_spread": round(three_month - fedfunds, 4),
        "two_year_change_20d": two_change,
        "five_year_change_20d": five_change,
        "ten_year_change_20d": ten_change,
        "thirty_year_change_20d": thirty_change,
        "belly_relative_move": belly_relative_move,
        "funding_pressure_signal": funding_pressure_signal(sofr - fedfunds, three_month - fedfunds),
        "carry_signal": carry_signal,
        "rates_regime": carry_signal,
    }
