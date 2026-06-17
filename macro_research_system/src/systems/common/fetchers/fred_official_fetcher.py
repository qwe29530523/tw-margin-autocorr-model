from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd

from src.systems.common.api_key_preflight import run_api_key_preflight
from src.systems.common.macro_series_schema import (
    normalize_observation_records,
    utc_fetched_at,
    validate_macro_series_frame,
)


FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"
SOURCE_NAME = "FRED"
SOURCE_TYPE = "official_public_macro"
API_KEY_ENV = "FRED_API_KEY"


class FREDConfigurationError(RuntimeError):
    pass


class FREDFetchError(RuntimeError):
    pass


def fetch_fred_series(
    series_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    session: Any | None = None,
    repo_root: str | Path | None = None,
    timeout: int = 20,
) -> pd.DataFrame:
    api_key = _require_fred_api_key(repo_root=repo_root)
    request_url = _build_observations_url(series_id, api_key, start_date=start_date, end_date=end_date)
    payload = _request_json(request_url, session=session, timeout=timeout)
    return normalize_fred_observations(
        series_id=series_id,
        observations=payload.get("observations", []),
        metadata=payload.get("series_metadata") or {},
    )


def fetch_fred_series_batch(
    series_ids: list[str],
    start_date: str | None = None,
    end_date: str | None = None,
    session: Any | None = None,
    repo_root: str | Path | None = None,
    timeout: int = 20,
) -> pd.DataFrame:
    frames = [
        fetch_fred_series(
            series_id,
            start_date=start_date,
            end_date=end_date,
            session=session,
            repo_root=repo_root,
            timeout=timeout,
        )
        for series_id in series_ids
    ]
    if not frames:
        return pd.DataFrame()
    return validate_macro_series_frame(pd.concat(frames, ignore_index=True))


def normalize_fred_observations(
    series_id: str,
    observations: list[dict[str, Any]],
    metadata: dict[str, Any] | None = None,
) -> pd.DataFrame:
    metadata = metadata or {}
    normalized_metadata = {
        "series_id": str(metadata.get("id") or series_id),
        "series_name": str(metadata.get("title") or metadata.get("series_name") or series_id),
        "source_name": SOURCE_NAME,
        "source_type": SOURCE_TYPE,
        "frequency": str(metadata.get("frequency") or metadata.get("frequency_short") or "unknown"),
        "unit": str(metadata.get("units") or metadata.get("unit") or "unknown"),
        "seasonal_adjustment": str(
            metadata.get("seasonal_adjustment") or metadata.get("seasonal_adjustment_short") or "unknown"
        ),
        "fetched_at": utc_fetched_at(),
    }
    return normalize_observation_records(observations, normalized_metadata)


def _require_fred_api_key(repo_root: str | Path | None = None) -> str:
    _load_preflight_env(repo_root)
    api_key = os.getenv(API_KEY_ENV)
    if not api_key:
        raise FREDConfigurationError(f"{API_KEY_ENV} is required for FRED official macro data fetch.")
    return api_key


def _load_preflight_env(repo_root: str | Path | None) -> None:
    try:
        run_api_key_preflight(repo_root=repo_root)
    except FileNotFoundError:
        return


def _build_observations_url(
    series_id: str,
    api_key: str,
    start_date: str | None,
    end_date: str | None,
) -> str:
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
    }
    if start_date:
        params["observation_start"] = start_date
    if end_date:
        params["observation_end"] = end_date
    return f"{FRED_OBSERVATIONS_URL}?{urllib.parse.urlencode(params)}"


def _request_json(url: str, session: Any | None, timeout: int) -> dict[str, Any]:
    opener = session or urllib.request
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with opener.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise FREDFetchError(f"FRED API request failed with HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise FREDFetchError(f"FRED API network error: {type(reason).__name__}") from exc
    except TimeoutError as exc:
        raise FREDFetchError("FRED API network timeout") from exc
    except json.JSONDecodeError as exc:
        raise FREDFetchError("FRED API malformed response: invalid JSON") from exc
