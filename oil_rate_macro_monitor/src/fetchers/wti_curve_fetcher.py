from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd
import requests

from ..utils.logging import get_logger


WTI_CURVE_COLUMNS = [
    "date",
    "cl_m1_settle",
    "cl_m2_settle",
    "cl_m3_settle",
    "source",
    "source_type",
]
ALLOWED_SOURCE_TYPES = {
    "production_api",
    "production_vendor",
    "research_manual",
    "historical_only",
}
DEFAULT_FIELD_MAP = {
    "date": "date",
    "cl_m1_settle": "cl_m1_settle",
    "cl_m2_settle": "cl_m2_settle",
    "cl_m3_settle": "cl_m3_settle",
    "source": "source",
    "source_type": "source_type",
}

logger = get_logger(__name__)


def empty_wti_curve_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=WTI_CURVE_COLUMNS)


def fetch_wti_curve_api(
    api_url: str | None,
    api_key: str | None,
    source: str = "wti_curve_api",
    source_type: str = "production_api",
    field_map: Mapping[str, str] | None = None,
    api_key_header: str = "Authorization",
    api_key_prefix: str = "Bearer",
    timeout: int = 30,
) -> pd.DataFrame:
    """Fetch provider-agnostic CL M1/M2/M3 settlements from a configured formal API.

    The endpoint is intentionally not hard-coded. Providers differ in paths,
    auth headers, and response envelopes, so callers must provide the endpoint
    and, if needed, a field map. Missing credentials are treated as unavailable
    upstream data, not as fatal errors.
    """
    if not api_url or not api_key:
        logger.warning("missing_wti_curve_upstream: WTI curve API URL or key is missing.")
        return empty_wti_curve_frame()

    headers = _auth_headers(api_key, api_key_header, api_key_prefix)
    try:
        response = requests.get(api_url, headers=headers, timeout=timeout)
        response.raise_for_status()
        records = _extract_records(response.json())
        if not records:
            logger.warning("missing_wti_curve_upstream: WTI curve API returned no records.")
            return empty_wti_curve_frame()
        return standardize_wti_curve_frame(
            pd.DataFrame(records),
            source=source,
            source_type=source_type,
            field_map=field_map,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("missing_wti_curve_upstream: WTI curve API fetch failed: %s", exc)
        return empty_wti_curve_frame()


def standardize_wti_curve_frame(
    frame: pd.DataFrame,
    source: str | None = None,
    source_type: str | None = None,
    field_map: Mapping[str, str] | None = None,
) -> pd.DataFrame:
    """Normalize a formal WTI contract ladder into the project contract schema."""
    if frame.empty:
        return empty_wti_curve_frame()
    if _looks_like_yahoo_front_month(frame):
        logger.warning("missing_wti_curve_upstream: Yahoo CL=F cannot be used as WTI M1/M2/M3 curve data.")
        return empty_wti_curve_frame()

    mapping = {**DEFAULT_FIELD_MAP, **(dict(field_map) if field_map else {})}
    rename_map = {provider_field: standard_field for standard_field, provider_field in mapping.items()}
    out = frame.rename(columns=rename_map).copy()
    missing_columns = [column for column in WTI_CURVE_COLUMNS[:4] if column not in out.columns]
    if missing_columns:
        logger.warning(
            "missing_wti_curve_upstream: WTI curve source is missing required columns: %s",
            ", ".join(missing_columns),
        )
        return empty_wti_curve_frame()

    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for column in ["cl_m1_settle", "cl_m2_settle", "cl_m3_settle"]:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    out["source"] = out.get("source", source or "wti_curve_api")
    out["source_type"] = out.get("source_type", source_type or "production_api")
    out["source_type"] = out["source_type"].fillna(source_type or "production_api").astype(str)
    invalid_source_type = ~out["source_type"].isin(ALLOWED_SOURCE_TYPES)
    if invalid_source_type.any():
        logger.warning("missing_wti_curve_upstream: WTI curve source_type is not supported.")
        return empty_wti_curve_frame()
    out = out.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    if out.empty:
        return empty_wti_curve_frame()
    return out[WTI_CURVE_COLUMNS]


def _auth_headers(api_key: str, api_key_header: str, api_key_prefix: str) -> dict[str, str]:
    if api_key_header.lower() == "authorization" and api_key_prefix:
        return {api_key_header: f"{api_key_prefix} {api_key}"}
    return {api_key_header: api_key}


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ["data", "results", "records", "items"]:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    response_data = payload.get("response", {}).get("data") if isinstance(payload.get("response"), dict) else None
    if isinstance(response_data, list):
        return [item for item in response_data if isinstance(item, dict)]
    return []


def _looks_like_yahoo_front_month(frame: pd.DataFrame) -> bool:
    if not {"ticker", "close"}.issubset(frame.columns):
        return False
    tickers = frame["ticker"].astype(str).str.upper()
    return tickers.isin({"CL=F", "BZ=F", "RB=F", "HO=F"}).any()
