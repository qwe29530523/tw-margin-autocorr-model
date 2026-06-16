from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

import pandas as pd


DEFAULT_API_BASE_URL = "https://api.metalpriceapi.com/v1"
DEFAULT_BASE = "USD"
SOURCE_NAME = "MetalPriceAPI"
SOURCE_TYPE = "research_only_benchmark"
API_KEY_ENV = "METALPRICE_API_KEY"
SUPPORTED_SYMBOLS = ("WTI", "BRENT", "NATURALGAS", "GASOLINE")
OUTPUT_COLUMNS = [
    "date",
    "symbol",
    "price",
    "base",
    "source",
    "source_type",
    "fetched_at",
    "raw_timestamp",
]


class MetalPriceAPIError(RuntimeError):
    pass


def fetch_latest_energy_benchmarks(
    symbols: list[str] | None = None,
    base: str = DEFAULT_BASE,
    api_base_url: str = DEFAULT_API_BASE_URL,
    timeout: int = 20,
) -> pd.DataFrame:
    requested_symbols = _validate_symbols(symbols)
    api_key = _api_key_from_env()
    url = _build_url(api_base_url, "latest", base, requested_symbols)
    payload = _request_json(url, api_key, timeout)
    return _normalize_payload(payload, requested_symbols, fallback_date=None)


def fetch_historical_energy_benchmarks(
    date: str,
    symbols: list[str] | None = None,
    base: str = DEFAULT_BASE,
    api_base_url: str = DEFAULT_API_BASE_URL,
    timeout: int = 20,
) -> pd.DataFrame:
    requested_symbols = _validate_symbols(symbols)
    api_key = _api_key_from_env()
    safe_date = str(pd.to_datetime(date).date())
    url = _build_url(api_base_url, safe_date, base, requested_symbols)
    payload = _request_json(url, api_key, timeout)
    return _normalize_payload(payload, requested_symbols, fallback_date=safe_date)


def _api_key_from_env() -> str:
    api_key = os.getenv(API_KEY_ENV)
    if not api_key:
        raise MetalPriceAPIError(f"{API_KEY_ENV} is required for MetalPriceAPI research-only benchmark fetch.")
    return api_key


def _validate_symbols(symbols: list[str] | None) -> list[str]:
    requested = list(symbols or SUPPORTED_SYMBOLS)
    unsupported = sorted(set(requested) - set(SUPPORTED_SYMBOLS))
    if unsupported:
        raise MetalPriceAPIError(f"Unsupported symbol(s) for MetalPriceAPI energy benchmark: {', '.join(unsupported)}")
    return requested


def _build_url(api_base_url: str, endpoint: str, base: str, symbols: list[str]) -> str:
    clean_base_url = api_base_url.rstrip("/")
    params = urllib.parse.urlencode(
        {
            "base": base,
            "currencies": ",".join(symbols),
        }
    )
    return f"{clean_base_url}/{endpoint}?{params}"


def _request_json(url: str, api_key: str, timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"X-API-KEY": api_key, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        reason = _http_error_reason(exc.code)
        raise MetalPriceAPIError(f"MetalPriceAPI {reason}: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise MetalPriceAPIError(f"MetalPriceAPI network error: {type(reason).__name__}") from exc
    except TimeoutError as exc:
        raise MetalPriceAPIError("MetalPriceAPI network timeout") from exc
    except json.JSONDecodeError as exc:
        raise MetalPriceAPIError("MetalPriceAPI malformed response: invalid JSON") from exc


def _normalize_payload(
    payload: dict[str, Any],
    symbols: list[str],
    fallback_date: str | None,
) -> pd.DataFrame:
    if payload.get("success") is False:
        message = _extract_error_message(payload)
        raise MetalPriceAPIError(f"MetalPriceAPI error response: {message}")

    rates = payload.get("rates")
    if not isinstance(rates, dict) or not rates:
        raise MetalPriceAPIError("MetalPriceAPI response contains no data for requested energy benchmark symbols.")

    base = str(payload.get("base") or DEFAULT_BASE)
    raw_timestamp = payload.get("timestamp") or payload.get("time_last_update_unix")
    date_value = payload.get("date") or _date_from_timestamp(raw_timestamp) or fallback_date
    if date_value is None:
        date_value = datetime.now(timezone.utc).date().isoformat()
    fetched_at = datetime.now(timezone.utc).isoformat()

    rows = []
    for symbol in symbols:
        value = rates.get(symbol)
        if value is None:
            continue
        try:
            price = float(value)
        except (TypeError, ValueError):
            continue
        rows.append(
            {
                "date": pd.to_datetime(date_value),
                "symbol": symbol,
                "price": price,
                "base": base,
                "source": SOURCE_NAME,
                "source_type": SOURCE_TYPE,
                "fetched_at": fetched_at,
                "raw_timestamp": raw_timestamp,
            }
        )

    if not rows:
        raise MetalPriceAPIError("MetalPriceAPI response contains no data for requested energy benchmark symbols.")
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def _date_from_timestamp(raw_timestamp: Any) -> str | None:
    try:
        return datetime.fromtimestamp(float(raw_timestamp), tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _extract_error_message(payload: dict[str, Any]) -> str:
    error = payload.get("error")
    if isinstance(error, dict):
        return str(error.get("type") or error.get("message") or "unknown error")
    if error:
        return str(error)
    return "unknown error"


def _http_error_reason(status_code: int) -> str:
    if status_code in {401, 403}:
        return "auth error"
    if status_code == 429:
        return "quota exceeded"
    return "HTTP error"
