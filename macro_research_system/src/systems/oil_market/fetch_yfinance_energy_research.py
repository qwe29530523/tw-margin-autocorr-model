from __future__ import annotations

import os
from typing import Iterable

import pandas as pd


DEFAULT_SYMBOLS = ["CL=F", "RB=F", "HO=F"]
SOURCE_NAME = "YAHOO_YFINANCE"
SOURCE_TYPE = "research_only_public_proxy"
DATA_STATUS = "RESEARCH_ONLY"
CAVEAT = (
    "Yahoo/yfinance data is research-only and cannot replace CME CL/RB/HO contract-month settlements "
    "or WTI M1/M2/M3 futures curve data."
)
OUTPUT_COLUMNS = ["date", "symbol", "close", "source_name", "source_type", "data_status", "caveat"]


def fetch_yfinance_energy_research_prices(
    symbols: Iterable[str] | None = None,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    requested_symbols = list(symbols or DEFAULT_SYMBOLS)
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError("yfinance is required for research-only energy futures proxy fetching.") from exc

    payload = yf.download(requested_symbols, start=start, end=end, progress=False, auto_adjust=False)
    return _normalize_yfinance_prices(payload, requested_symbols)


def _normalize_yfinance_prices(payload: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    if payload is None or payload.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    rows: list[dict[str, object]] = []
    for symbol in symbols:
        close = _close_series(payload, symbol, len(symbols) == 1)
        if close is None:
            continue
        for date_value, value in close.items():
            rows.append(
                {
                    "date": pd.to_datetime(date_value),
                    "symbol": symbol,
                    "close": pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0],
                    "source_name": SOURCE_NAME,
                    "source_type": SOURCE_TYPE,
                    "data_status": DATA_STATUS,
                    "caveat": CAVEAT,
                }
            )

    if not rows:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS).sort_values(["date", "symbol"]).reset_index(drop=True)


def _close_series(payload: pd.DataFrame, symbol: str, single_symbol: bool) -> pd.Series | None:
    if isinstance(payload.columns, pd.MultiIndex):
        if ("Close", symbol) in payload.columns:
            return payload[("Close", symbol)]
        if (symbol, "Close") in payload.columns:
            return payload[(symbol, "Close")]
        return None

    if single_symbol and "Close" in payload.columns:
        return payload["Close"]
    if symbol in payload.columns:
        return payload[symbol]
    return None
