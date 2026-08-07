from __future__ import annotations

import pandas as pd


SOURCE_NAME = "YAHOO_YFINANCE"
SOURCE_TYPE = "research_only_public_proxy"
DATA_STATUS = "RESEARCH_ONLY"
GALLONS_PER_BARREL = 42
CAVEAT = (
    "Crack spread proxies are derived from Yahoo/yfinance continuous front-month proxies and are not "
    "official CME CL/RB/HO contract-month settlement spreads."
)
OUTPUT_COLUMNS = [
    "date",
    "wti_front_month_proxy",
    "rbob_front_month_proxy",
    "heating_oil_front_month_proxy",
    "gasoline_crack_research_proxy",
    "distillate_crack_research_proxy",
    "crack_321_research_proxy",
    "source_name",
    "source_type",
    "data_status",
    "caveat",
]


def calculate_research_crack_spreads(price_df: pd.DataFrame) -> pd.DataFrame:
    if price_df.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    required = {"date", "symbol", "close"}
    missing = required - set(price_df.columns)
    if missing:
        raise ValueError(f"Missing required research price column(s): {', '.join(sorted(missing))}")

    frame = price_df.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    wide = (
        frame.pivot_table(index="date", columns="symbol", values="close", aggfunc="last")
        .rename(
            columns={
                "CL=F": "wti_front_month_proxy",
                "RB=F": "rbob_front_month_proxy",
                "HO=F": "heating_oil_front_month_proxy",
            }
        )
        .reset_index()
    )

    for column in ["wti_front_month_proxy", "rbob_front_month_proxy", "heating_oil_front_month_proxy"]:
        if column not in wide.columns:
            wide[column] = pd.NA

    wide["gasoline_crack_research_proxy"] = (wide["rbob_front_month_proxy"] * GALLONS_PER_BARREL) - wide[
        "wti_front_month_proxy"
    ]
    wide["distillate_crack_research_proxy"] = (wide["heating_oil_front_month_proxy"] * GALLONS_PER_BARREL) - wide[
        "wti_front_month_proxy"
    ]
    wide["crack_321_research_proxy"] = (
        (2 * wide["rbob_front_month_proxy"] * GALLONS_PER_BARREL)
        + (wide["heating_oil_front_month_proxy"] * GALLONS_PER_BARREL)
        - (3 * wide["wti_front_month_proxy"])
    ) / 3
    wide["source_name"] = SOURCE_NAME
    wide["source_type"] = SOURCE_TYPE
    wide["data_status"] = DATA_STATUS
    wide["caveat"] = CAVEAT
    return wide[OUTPUT_COLUMNS].sort_values("date").reset_index(drop=True)
