from __future__ import annotations

from typing import Iterable

import pandas as pd

from src.utils.logging import get_logger


DEFAULT_YAHOO_TICKERS = [
    "CL=F",
    "BZ=F",
    "RB=F",
    "HO=F",
    "DX-Y.NYB",
    "^TNX",
    "^IRX",
    "SPY",
    "QQQ",
    "TLT",
    "HYG",
]

logger = get_logger(__name__)


def empty_yahoo_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"])


def _standardize_price_frame(frame: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if frame.empty:
        return empty_yahoo_frame()
    out = frame.reset_index()
    date_column = "Date" if "Date" in out.columns else out.columns[0]
    out = out.rename(
        columns={
            date_column: "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adj_close",
            "Volume": "volume",
        }
    )
    if "adj_close" not in out.columns:
        out["adj_close"] = out.get("close")
    if "volume" not in out.columns:
        out["volume"] = pd.NA
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["ticker"] = ticker
    columns = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]
    for column in columns:
        if column not in out.columns:
            out[column] = pd.NA
    return out[columns].dropna(subset=["date"])


def fetch_yahoo_prices(
    tickers: Iterable[str] = DEFAULT_YAHOO_TICKERS,
    period: str = "5y",
    interval: str = "1d",
) -> pd.DataFrame:
    ticker_list = list(tickers)
    try:
        import yfinance as yf

        data = yf.download(
            ticker_list,
            period=period,
            interval=interval,
            group_by="ticker",
            auto_adjust=False,
            progress=False,
            threads=True,
            timeout=30,
        )
        if data.empty:
            return empty_yahoo_frame()
        frames: list[pd.DataFrame] = []
        if isinstance(data.columns, pd.MultiIndex):
            for ticker in ticker_list:
                if ticker in data.columns.get_level_values(0):
                    frames.append(_standardize_price_frame(data[ticker], ticker))
        else:
            frames.append(_standardize_price_frame(data, ticker_list[0]))
        if not frames:
            return empty_yahoo_frame()
        return pd.concat(frames, ignore_index=True)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Yahoo fetch failed: %s", exc)
        return empty_yahoo_frame()
