import pandas as pd

from src.processors.rates_curve_engine import build_rates_curve_frame

RATES_COLUMNS = [
    "date",
    "ten_year",
    "two_year",
    "three_month",
    "T10Y2Y",
    "T10Y3M",
    "ten_year_change_5d",
    "two_year_change_5d",
    "ten_year_change_20d",
    "two_year_change_20d",
    "ten_year_change_60d",
    "two_year_change_60d",
    "ten_year_two_year_spread",
    "ten_year_three_month_spread",
    "rates_curve_asof_date",
    "spread_change_20d",
    "belly_relative_move",
    "curve_direction",
    "rate_signal",
    "ten_year_asof_date",
    "two_year_asof_date",
    "three_month_asof_date",
    "ten_year_two_year_spread_asof_date",
    "ten_year_three_month_spread_asof_date",
    "fred_rates_asof_date",
]


def process_rates(fred_data: pd.DataFrame) -> pd.DataFrame:
    out = build_rates_curve_frame(fred_data)
    if out.empty:
        return pd.DataFrame(columns=RATES_COLUMNS)
    out["T10Y2Y"] = out.get("ten_year_two_year_spread_fred", out["ten_year_two_year_spread"])
    out["T10Y3M"] = out.get("ten_year_three_month_spread_fred", out["ten_year_three_month_spread"])
    out["spread_change_20d"] = out["ten_year_two_year_spread"].diff(20)
    out["curve_direction"] = out["curve_slope_state"]
    out["rate_signal"] = out["rates_regime"]
    for column in RATES_COLUMNS:
        if column not in out.columns:
            out[column] = pd.NA
    return out[RATES_COLUMNS]


def _rate_signal(row: pd.Series) -> str:
    ten_year_change = row.get("ten_year_change_20d", np.nan)
    spread_change = row.get("spread_change_20d", np.nan)
    ten_two = row.get("ten_year_two_year_spread", np.nan)
    ten_three_month = row.get("ten_year_three_month_spread", np.nan)
    if (pd.notna(ten_three_month) and ten_three_month < 0) or (pd.notna(ten_two) and ten_two < 0):
        return "inversion_pressure"
    if pd.notna(ten_year_change) and pd.notna(spread_change) and ten_year_change > 0 and spread_change > 0:
        return "curve_bear_steepening"
    if pd.notna(ten_year_change) and pd.notna(spread_change) and ten_year_change < 0 and spread_change > 0:
        return "curve_bull_steepening"
    if pd.notna(ten_year_change) and ten_year_change > 0.25:
        return "rates_up"
    if pd.notna(ten_year_change) and ten_year_change < -0.25:
        return "rates_down"
    return "mixed"
