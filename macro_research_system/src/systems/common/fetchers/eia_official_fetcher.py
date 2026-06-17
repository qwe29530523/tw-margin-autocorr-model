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


EIA_API_BASE_URL = "https://api.eia.gov/v2"
SOURCE_NAME = "EIA"
SOURCE_TYPE = "official_public_energy"
API_KEY_ENV = "EIA_API_KEY"


class EIAConfigurationError(RuntimeError):
    pass


class EIAFetchError(RuntimeError):
    pass


def fetch_eia_series(
    series_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    session: Any | None = None,
    repo_root: str | Path | None = None,
    route: str | None = None,
    timeout: int = 20,
) -> pd.DataFrame:
    api_key = _require_eia_api_key(repo_root=repo_root)
    request_url = _build_eia_url(series_id, api_key, start_date=start_date, end_date=end_date, route=route)
    payload = _request_json(request_url, session=session, timeout=timeout)
    return normalize_eia_observations(
        series_id=series_id,
        observations=_extract_observations(payload),
        metadata=_extract_metadata(series_id, payload),
    )


def fetch_eia_series_batch(
    series_ids: list[str],
    start_date: str | None = None,
    end_date: str | None = None,
    session: Any | None = None,
    repo_root: str | Path | None = None,
    timeout: int = 20,
) -> pd.DataFrame:
    frames = [
        fetch_eia_series(
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


def normalize_eia_observations(
    series_id: str,
    observations: list[dict[str, Any]],
    metadata: dict[str, Any] | None = None,
) -> pd.DataFrame:
    metadata = metadata or {}
    normalized_records = [_normalize_eia_record(record) for record in observations]
    normalized_metadata = {
        "series_id": series_id,
        "series_name": str(metadata.get("series_name") or metadata.get("name") or metadata.get("title") or series_id),
        "source_name": SOURCE_NAME,
        "source_type": SOURCE_TYPE,
        "frequency": str(metadata.get("frequency") or _infer_frequency(observations)),
        "unit": str(metadata.get("unit") or metadata.get("units") or _first_units(observations) or "unknown"),
        "seasonal_adjustment": str(metadata.get("seasonal_adjustment") or "unknown"),
        "fetched_at": utc_fetched_at(),
    }
    return normalize_observation_records(normalized_records, normalized_metadata)


def _require_eia_api_key(repo_root: str | Path | None = None) -> str:
    _load_preflight_env(repo_root)
    api_key = os.getenv(API_KEY_ENV)
    if not api_key:
        raise EIAConfigurationError(f"{API_KEY_ENV} is required for EIA official energy data fetch.")
    return api_key


def _load_preflight_env(repo_root: str | Path | None) -> None:
    try:
        run_api_key_preflight(repo_root=repo_root)
    except FileNotFoundError:
        return


def _build_eia_url(
    series_id: str,
    api_key: str,
    start_date: str | None,
    end_date: str | None,
    route: str | None,
) -> str:
    if route:
        return _build_route_url(series_id, api_key, start_date=start_date, end_date=end_date, route=route)
    params = {
        "api_key": api_key,
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        "length": "5000",
    }
    if start_date:
        params["start"] = start_date
    if end_date:
        params["end"] = end_date
    safe_series_id = urllib.parse.quote(series_id, safe="")
    return f"{EIA_API_BASE_URL}/seriesid/{safe_series_id}?{urllib.parse.urlencode(params)}"


def _build_route_url(
    series_id: str,
    api_key: str,
    start_date: str | None,
    end_date: str | None,
    route: str,
) -> str:
    params: list[tuple[str, str]] = [
        ("api_key", api_key),
        ("data[0]", "value"),
        ("facets[series][]", series_id),
        ("sort[0][column]", "period"),
        ("sort[0][direction]", "asc"),
        ("length", "5000"),
    ]
    if start_date:
        params.append(("start", start_date))
    if end_date:
        params.append(("end", end_date))
    clean_route = route.strip("/")
    return f"{EIA_API_BASE_URL}/{clean_route}/data/?{urllib.parse.urlencode(params)}"


def _request_json(url: str, session: Any | None, timeout: int) -> dict[str, Any]:
    opener = session or urllib.request
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with opener.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise EIAFetchError(f"EIA API request failed with HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise EIAFetchError(f"EIA API network error: {type(reason).__name__}") from exc
    except TimeoutError as exc:
        raise EIAFetchError("EIA API network timeout") from exc
    except json.JSONDecodeError as exc:
        raise EIAFetchError("EIA API malformed response: invalid JSON") from exc


def _extract_observations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    response = payload.get("response")
    if isinstance(response, dict) and isinstance(response.get("data"), list):
        return response["data"]
    if isinstance(payload.get("data"), list):
        return payload["data"]
    return []


def _extract_metadata(series_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = payload.get("response")
    metadata: dict[str, Any] = {"series_id": series_id}
    if isinstance(response, dict):
        metadata.update({key: value for key, value in response.items() if key in {"name", "description", "frequency"}})
    for key in ["series_name", "name", "title", "frequency", "unit", "units"]:
        if key in payload:
            metadata[key] = payload[key]
    if "description" in metadata and "series_name" not in metadata:
        metadata["series_name"] = metadata["description"]
    return metadata


def _normalize_eia_record(record: dict[str, Any]) -> dict[str, Any]:
    notes = _notes_from_record(record)
    normalized: dict[str, Any] = {
        "date": _eia_period_to_date(record.get("period") or record.get("date")),
        "value": _coerce_eia_value(record.get("value")),
        "observation_status": record.get("frequency") or record.get("series"),
    }
    if notes:
        normalized["notes"] = notes
    return normalized


def _eia_period_to_date(value: Any) -> str | None:
    if value is None:
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date().isoformat()


def _coerce_eia_value(value: Any) -> Any:
    if value in {None, ".", "", "-", "--", "NA", "N/A", "W", "not_available"}:
        return pd.NA
    return value


def _infer_frequency(observations: list[dict[str, Any]]) -> str:
    values = [str(item.get("period") or item.get("date") or "") for item in observations if item.get("period") or item.get("date")]
    if not values:
        return "unknown"
    if all(len(value) >= 10 for value in values):
        return "daily_or_weekly"
    if all(len(value) == 7 for value in values):
        return "monthly"
    if all(len(value) == 4 for value in values):
        return "annual"
    return "unknown"


def _first_units(observations: list[dict[str, Any]]) -> Any:
    for item in observations:
        if item.get("units"):
            return item.get("units")
    return None


def _notes_from_record(record: dict[str, Any]) -> str | None:
    for key in ["units", "series-description"]:
        if record.get(key):
            return str(record[key])
    return None
