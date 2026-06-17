from __future__ import annotations

import json
import os
import urllib.error
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


BLS_TIMESERIES_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
SOURCE_NAME = "BLS"
SOURCE_TYPE = "official_public_labor_inflation"
API_KEY_ENV = "BLS_API_KEY"


class BLSConfigurationError(RuntimeError):
    pass


class BLSFetchError(RuntimeError):
    pass


def fetch_bls_series(
    series_id: str,
    start_year: int | str | None = None,
    end_year: int | str | None = None,
    session: Any | None = None,
    repo_root: str | Path | None = None,
    timeout: int = 20,
) -> pd.DataFrame:
    return fetch_bls_series_batch(
        [series_id],
        start_year=start_year,
        end_year=end_year,
        session=session,
        repo_root=repo_root,
        timeout=timeout,
    )


def fetch_bls_series_batch(
    series_ids: list[str],
    start_year: int | str | None = None,
    end_year: int | str | None = None,
    session: Any | None = None,
    repo_root: str | Path | None = None,
    timeout: int = 20,
) -> pd.DataFrame:
    api_key = _require_bls_api_key(repo_root=repo_root)
    payload = _build_payload(series_ids, api_key, start_year=start_year, end_year=end_year)
    response = _request_json(payload, session=session, timeout=timeout)
    if response.get("status") != "REQUEST_SUCCEEDED":
        raise BLSFetchError("BLS API request did not succeed.")

    series_items = response.get("Results", {}).get("series", [])
    frames = [
        normalize_bls_observations(
            series_id=str(item.get("seriesID") or ""),
            observations=item.get("data", []),
        )
        for item in series_items
        if item.get("seriesID")
    ]
    if not frames:
        return pd.DataFrame()
    return validate_macro_series_frame(pd.concat(frames, ignore_index=True))


def normalize_bls_observations(
    series_id: str,
    observations: list[dict[str, Any]],
    metadata: dict[str, Any] | None = None,
) -> pd.DataFrame:
    metadata = metadata or {}
    normalized_records = [_normalize_bls_record(record) for record in observations]
    normalized_metadata = {
        "series_id": series_id,
        "series_name": str(metadata.get("series_name") or metadata.get("title") or series_id),
        "source_name": SOURCE_NAME,
        "source_type": SOURCE_TYPE,
        "frequency": str(metadata.get("frequency") or _infer_frequency(observations)),
        "unit": str(metadata.get("unit") or metadata.get("units") or "unknown"),
        "seasonal_adjustment": str(metadata.get("seasonal_adjustment") or "unknown"),
        "fetched_at": utc_fetched_at(),
    }
    return normalize_observation_records(normalized_records, normalized_metadata)


def _require_bls_api_key(repo_root: str | Path | None = None) -> str:
    _load_preflight_env(repo_root)
    api_key = os.getenv(API_KEY_ENV)
    if not api_key:
        raise BLSConfigurationError(f"{API_KEY_ENV} is required for BLS official inflation and labor data fetch.")
    return api_key


def _load_preflight_env(repo_root: str | Path | None) -> None:
    try:
        run_api_key_preflight(repo_root=repo_root)
    except FileNotFoundError:
        return


def _build_payload(
    series_ids: list[str],
    api_key: str,
    start_year: int | str | None,
    end_year: int | str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "seriesid": series_ids,
        "registrationkey": api_key,
    }
    if start_year is not None:
        payload["startyear"] = str(start_year)
    if end_year is not None:
        payload["endyear"] = str(end_year)
    return payload


def _request_json(payload: dict[str, Any], session: Any | None, timeout: int) -> dict[str, Any]:
    opener = session or urllib.request
    request = urllib.request.Request(
        BLS_TIMESERIES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with opener.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise BLSFetchError(f"BLS API request failed with HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise BLSFetchError(f"BLS API network error: {type(reason).__name__}") from exc
    except TimeoutError as exc:
        raise BLSFetchError("BLS API network timeout") from exc
    except json.JSONDecodeError as exc:
        raise BLSFetchError("BLS API malformed response: invalid JSON") from exc


def _normalize_bls_record(record: dict[str, Any]) -> dict[str, Any]:
    notes = _footnote_notes(record.get("footnotes"))
    normalized: dict[str, Any] = {
        "date": _bls_period_to_date(record.get("year"), record.get("period")),
        "value": record.get("value"),
        "observation_status": record.get("periodName"),
    }
    if notes:
        normalized["notes"] = notes
    return normalized


def _bls_period_to_date(year: Any, period: Any) -> str | None:
    try:
        year_int = int(year)
    except (TypeError, ValueError):
        return None

    period_text = str(period or "").upper()
    if period_text.startswith("M"):
        try:
            month = int(period_text[1:])
        except ValueError:
            return None
        if 1 <= month <= 12:
            return f"{year_int:04d}-{month:02d}-01"
        if month == 13:
            return f"{year_int:04d}-01-01"
    if period_text.startswith("Q"):
        try:
            quarter = int(period_text[1:])
        except ValueError:
            return None
        if 1 <= quarter <= 4:
            month = (quarter - 1) * 3 + 1
            return f"{year_int:04d}-{month:02d}-01"
    if period_text.startswith("A"):
        return f"{year_int:04d}-01-01"
    return None


def _infer_frequency(observations: list[dict[str, Any]]) -> str:
    periods = {str(item.get("period") or "").upper() for item in observations}
    if any(period.startswith("M") for period in periods):
        return "monthly"
    if any(period.startswith("Q") for period in periods):
        return "quarterly"
    if any(period.startswith("A") for period in periods):
        return "annual"
    return "unknown"


def _footnote_notes(footnotes: Any) -> str | None:
    if not isinstance(footnotes, list):
        return None
    notes = [str(item.get("text")) for item in footnotes if isinstance(item, dict) and item.get("text")]
    if not notes:
        return None
    return "; ".join(notes)
