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


CENSUS_API_BASE_URL = "https://api.census.gov/data"
SOURCE_NAME = "Census"
SOURCE_TYPE = "official_public_real_economy"
API_KEY_ENV = "CENSUS_API_KEY"


class CensusConfigurationError(RuntimeError):
    pass


class CensusFetchError(RuntimeError):
    pass


def fetch_census_series(
    series_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    session: Any | None = None,
    repo_root: str | Path | None = None,
    dataset: str | None = None,
    variables: list[str] | None = None,
    geography: str | None = None,
    timeout: int = 20,
) -> pd.DataFrame:
    api_key = _require_census_api_key(repo_root=repo_root)
    resolved_dataset, resolved_variables, resolved_geography = _require_census_request_contract(
        dataset=dataset,
        variables=variables,
        geography=geography,
    )
    request_url = _build_census_url(
        api_key=api_key,
        start_date=start_date,
        end_date=end_date,
        dataset=resolved_dataset,
        variables=resolved_variables,
        geography=resolved_geography,
    )
    payload = _request_json(request_url, session=session, timeout=timeout)
    return normalize_census_observations(
        series_id=series_id,
        observations=_extract_observations(payload),
        metadata={
            "series_name": series_id,
            "dataset": resolved_dataset,
            "frequency": "monthly",
            "unit": "unknown",
            "seasonal_adjustment": "unknown",
        },
    )


def fetch_census_series_batch(
    series_ids: list[str],
    start_date: str | None = None,
    end_date: str | None = None,
    session: Any | None = None,
    repo_root: str | Path | None = None,
    dataset: str | None = None,
    variables: list[str] | None = None,
    geography: str | None = None,
    timeout: int = 20,
) -> pd.DataFrame:
    frames = [
        fetch_census_series(
            series_id,
            start_date=start_date,
            end_date=end_date,
            session=session,
            repo_root=repo_root,
            dataset=dataset,
            variables=variables,
            geography=geography,
            timeout=timeout,
        )
        for series_id in series_ids
    ]
    if not frames:
        return pd.DataFrame()
    return validate_macro_series_frame(pd.concat(frames, ignore_index=True))


def normalize_census_observations(
    series_id: str,
    observations: list[dict[str, Any]],
    metadata: dict[str, Any] | None = None,
) -> pd.DataFrame:
    metadata = metadata or {}
    normalized_records = [_normalize_census_record(record) for record in observations]
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


def _require_census_api_key(repo_root: str | Path | None = None) -> str:
    _load_preflight_env(repo_root)
    api_key = os.getenv(API_KEY_ENV)
    if not api_key:
        raise CensusConfigurationError(f"{API_KEY_ENV} is required for Census official housing and real economy data fetch.")
    return api_key


def _load_preflight_env(repo_root: str | Path | None) -> None:
    try:
        run_api_key_preflight(repo_root=repo_root)
    except FileNotFoundError:
        return


def _require_census_request_contract(
    dataset: str | None,
    variables: list[str] | None,
    geography: str | None,
) -> tuple[str, list[str], str]:
    if not dataset or not variables or not geography:
        raise CensusConfigurationError(
            "Census dataset, variables, and geography must be supplied from a verified source contract."
        )
    return dataset, variables, geography


def _build_census_url(
    api_key: str,
    start_date: str | None,
    end_date: str | None,
    dataset: str,
    variables: list[str],
    geography: str,
) -> str:
    params = {
        "get": ",".join(variables),
        "for": geography,
        "key": api_key,
    }
    if start_date and end_date:
        params["time"] = f"from {start_date} to {end_date}"
    elif start_date:
        params["time"] = f"from {start_date}"
    elif end_date:
        params["time"] = f"to {end_date}"
    clean_dataset = dataset.strip("/")
    return f"{CENSUS_API_BASE_URL}/{clean_dataset}?{urllib.parse.urlencode(params)}"


def _request_json(url: str, session: Any | None, timeout: int) -> Any:
    opener = session or urllib.request
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with opener.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise CensusFetchError(f"Census API request failed with HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise CensusFetchError(f"Census API network error: {type(reason).__name__}") from exc
    except TimeoutError as exc:
        raise CensusFetchError("Census API network timeout") from exc
    except json.JSONDecodeError as exc:
        raise CensusFetchError("Census API malformed response: invalid JSON") from exc


def _extract_observations(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return _records_from_census_table(payload)
    if isinstance(payload, dict):
        data = payload.get("data") or payload.get("response")
        if isinstance(data, list):
            return _records_from_census_table(data)
        if isinstance(payload.get("observations"), list):
            return payload["observations"]
    return []


def _records_from_census_table(table: list[Any]) -> list[dict[str, Any]]:
    if not table:
        return []
    if all(isinstance(item, dict) for item in table):
        return table
    header = table[0]
    if not isinstance(header, list):
        return []
    records: list[dict[str, Any]] = []
    for row in table[1:]:
        if isinstance(row, list):
            records.append({str(column): value for column, value in zip(header, row)})
    return records


def _normalize_census_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {
        "date": _census_period_to_date(
            record.get("date") or record.get("period") or record.get("time"),
            year=record.get("year") or record.get("YEAR"),
            month=record.get("month") or record.get("MONTH"),
        ),
        "value": _coerce_census_value(_first_present(record, ["value", "cell_value", "data_value", "estimate"])),
        "observation_status": record.get("NAME") or record.get("geo_name") or record.get("seasonally_adj"),
    }
    notes = _notes_from_record(record)
    if notes:
        normalized["notes"] = notes
    return normalized


def _census_period_to_date(value: Any, year: Any = None, month: Any = None) -> str | None:
    if value is None and year is not None and month is not None:
        value = f"{year}-{int(month):02d}"
    if value is None:
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date().isoformat()


def _coerce_census_value(value: Any) -> Any:
    if value in {None, ".", "", "-", "--", "NA", "N/A", "(X)", "not_available"}:
        return pd.NA
    return value


def _first_present(record: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in record:
            return record[key]
    return None


def _infer_frequency(observations: list[dict[str, Any]]) -> str:
    values = [
        str(item.get("time") or item.get("period") or item.get("date") or "")
        for item in observations
        if item.get("time") or item.get("period") or item.get("date")
    ]
    if not values:
        return "unknown"
    if all(len(value) >= 10 for value in values):
        return "daily_or_weekly"
    if all(len(value) == 7 for value in values):
        return "monthly"
    if all(len(value) == 4 for value in values):
        return "annual"
    return "unknown"


def _notes_from_record(record: dict[str, Any]) -> str | None:
    parts = []
    for key in ["NAME", "dataset", "seasonally_adj"]:
        if record.get(key):
            parts.append(str(record[key]))
    if not parts:
        return None
    return "; ".join(parts)
