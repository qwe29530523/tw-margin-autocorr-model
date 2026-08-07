from __future__ import annotations

import pandas as pd


SOURCE_NAME = "CFTC_COT"
SOURCE_TYPE = "official_public_positioning_data"
DATA_STATUS = "PUBLIC_DATA_SOURCE"
OUTPUT_COLUMNS = [
    "date",
    "market",
    "managed_money_long",
    "managed_money_short",
    "managed_money_net",
    "managed_money_net_percent_oi",
    "managed_money_short_percent_oi",
    "managed_money_net_percentile",
    "managed_money_short_percentile",
    "managed_money_1w_change",
    "managed_money_7w_change",
    "oil_positioning_state",
    "oil_squeeze_risk",
    "source_name",
    "source_type",
    "data_status",
]


def calculate_oil_positioning_squeeze(cot_df: pd.DataFrame, lookback_weeks: int = 156) -> pd.DataFrame:
    if cot_df.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    required = {"date", "market", "managed_money_long", "managed_money_short", "open_interest"}
    missing = required - set(cot_df.columns)
    if missing:
        raise ValueError(f"Missing required CFTC positioning column(s): {', '.join(sorted(missing))}")

    frame = cot_df.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    for column in ["managed_money_long", "managed_money_short", "open_interest"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.sort_values(["market", "date"]).reset_index(drop=True)

    frame["managed_money_net"] = frame["managed_money_long"] - frame["managed_money_short"]
    valid_oi = frame["open_interest"].where(frame["open_interest"] > 0)
    frame["managed_money_net_percent_oi"] = frame["managed_money_net"] / valid_oi
    frame["managed_money_short_percent_oi"] = frame["managed_money_short"] / valid_oi

    grouped = frame.groupby("market", group_keys=False)
    frame["managed_money_net_percentile"] = grouped["managed_money_net_percent_oi"].transform(
        lambda series: _rolling_percentile(series, lookback_weeks)
    )
    frame["managed_money_short_percentile"] = grouped["managed_money_short_percent_oi"].transform(
        lambda series: _rolling_percentile(series, lookback_weeks)
    )
    frame["managed_money_1w_change"] = grouped["managed_money_net"].diff(1)
    frame["managed_money_7w_change"] = grouped["managed_money_net"].diff(7)

    states_and_risks = frame.apply(_classify_row, axis=1, result_type="expand")
    frame["oil_positioning_state"] = states_and_risks[0]
    frame["oil_squeeze_risk"] = states_and_risks[1]
    frame["source_name"] = SOURCE_NAME
    frame["source_type"] = SOURCE_TYPE
    frame["data_status"] = frame["oil_positioning_state"].where(frame["oil_positioning_state"].eq("MISSING"), DATA_STATUS)
    return frame[OUTPUT_COLUMNS]


def _rolling_percentile(series: pd.Series, lookback_weeks: int) -> pd.Series:
    lookback = max(int(lookback_weeks), 1)

    def percentile(window: pd.Series) -> float:
        clean = pd.to_numeric(window, errors="coerce").dropna()
        if clean.empty:
            return float("nan")
        current = clean.iloc[-1]
        return float((clean <= current).sum() / len(clean))

    return series.rolling(window=lookback, min_periods=1).apply(percentile, raw=False)


def _classify_row(row: pd.Series) -> tuple[str, str]:
    if (
        pd.isna(row.get("managed_money_net_percent_oi"))
        or pd.isna(row.get("managed_money_short_percent_oi"))
        or pd.isna(row.get("managed_money_net_percentile"))
        or pd.isna(row.get("managed_money_short_percentile"))
    ):
        return "MISSING", "MISSING"

    short_pct = float(row["managed_money_short_percentile"])
    net_pct = float(row["managed_money_net_percentile"])
    one_week = row.get("managed_money_1w_change")
    seven_week = row.get("managed_money_7w_change")

    if short_pct >= 0.90 and net_pct <= 0.20 and _positive(one_week) and _positive(seven_week):
        return "SHORT_SQUEEZE_SETUP_CANDIDATE", "HIGH"
    if short_pct >= 0.95 and net_pct <= 0.25:
        return "EXTREME_CROWDED_SHORT", "HIGH"
    if short_pct >= 0.85 and net_pct <= 0.35:
        return "CROWDED_SHORT", "ELEVATED"
    if net_pct <= 0.20 and _negative(one_week):
        return "BEARISH_POSITIONING_CONFIRMATION", "ELEVATED"
    return "POSITIONING_NEUTRAL", "LOW"


def _positive(value: object) -> bool:
    return pd.notna(value) and float(value) > 0


def _negative(value: object) -> bool:
    return pd.notna(value) and float(value) < 0
