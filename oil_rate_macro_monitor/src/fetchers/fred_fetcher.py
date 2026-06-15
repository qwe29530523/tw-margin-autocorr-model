from __future__ import annotations

from typing import Iterable

import pandas as pd
import requests

from src.utils.logging import get_logger


FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"
DEFAULT_FRED_SERIES = [
    "FEDFUNDS",
    "SOFR",
    "DGS3MO",
    "DGS1",
    "DGS2",
    "DGS5",
    "DGS10",
    "DGS30",
    "T10Y2Y",
    "T10Y3M",
    "DCOILWTICO",
    "DCOILBRENTEU",
]

logger = get_logger(__name__)


def empty_fred_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=["date", "value", "series_id"])


def fetch_fred_series(
    series_id: str,
    observation_start: str | None = None,
    observation_end: str | None = None,
    api_key: str | None = None,
) -> pd.DataFrame:
    if not api_key:
        logger.warning("Skipping FRED series %s because FRED_API_KEY is missing.", series_id)
        return empty_fred_frame()

    params: dict[str, str] = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
    }
    if observation_start:
        params["observation_start"] = observation_start
    if observation_end:
        params["observation_end"] = observation_end

    try:
        response = requests.get(FRED_OBSERVATIONS_URL, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        observations = payload.get("observations", [])
        df = pd.DataFrame(observations)
        if df.empty:
            return empty_fred_frame()
        df = df[["date", "value"]].copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["value"] = pd.to_numeric(df["value"].replace(".", pd.NA), errors="coerce")
        df["series_id"] = series_id
        return df[["date", "value", "series_id"]].dropna(subset=["date"])
    except Exception as exc:  # noqa: BLE001
        logger.exception("FRED fetch failed for %s: %s", series_id, exc)
        return empty_fred_frame()


def fetch_many_fred_series(
    series_ids: Iterable[str] = DEFAULT_FRED_SERIES,
    observation_start: str | None = None,
    observation_end: str | None = None,
    api_key: str | None = None,
) -> pd.DataFrame:
    frames = [
        fetch_fred_series(series_id, observation_start, observation_end, api_key)
        for series_id in series_ids
    ]
    if not frames:
        return empty_fred_frame()
    return pd.concat(frames, ignore_index=True)
