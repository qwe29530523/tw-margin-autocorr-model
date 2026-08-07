from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from src.systems.common.macro_series_schema import validate_macro_series_frame


TODO_STATUSES = {
    "BLOCKED_VENDOR_NOT_CONFIGURED",
    "TODO_VERIFY",
    "TODO_VERIFY_CENSUS_ROUTE",
    "TODO_VERIFY_VENDOR_ROUTE",
}
WTI_M1_M2_M3_BLOCKER_STATUS = "open"


def load_domain_input_mappings(config_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(config_path) if config_path is not None else _default_mapping_path()
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError("Domain input mappings must be a mapping.")
    return payload


def build_domain_input(
    normalized_df: pd.DataFrame,
    domain_name: str,
    mappings: dict[str, Any] | None = None,
) -> pd.DataFrame:
    mapping_config = mappings or load_domain_input_mappings()
    domain_config = _domain_config(mapping_config, domain_name)
    frame = _validated_or_empty(normalized_df)
    dates = _date_frame(frame)

    result = dates.copy()
    for mapped_field, field_config in _domain_mappings(domain_config).items():
        if not _is_active_mapping(field_config):
            continue
        matched_series = _first_matching_series(frame, field_config.get("candidate_series") or [])
        if matched_series is None:
            continue
        series_values = (
            frame.loc[frame["series_id"].eq(matched_series), ["date", "value"]]
            .sort_values("date")
            .drop_duplicates("date", keep="last")
            .rename(columns={"value": mapped_field})
        )
        result = result.merge(series_values, on="date", how="left")

    return result


def build_all_domain_inputs(
    normalized_df: pd.DataFrame,
    mappings: dict[str, Any] | None = None,
) -> dict[str, pd.DataFrame]:
    mapping_config = mappings or load_domain_input_mappings()
    return {
        domain_name: build_domain_input(normalized_df, domain_name, mappings=mapping_config)
        for domain_name in mapping_config
    }


def build_domain_input_coverage(
    normalized_df: pd.DataFrame,
    domain_name: str,
    mappings: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    mapping_config = mappings or load_domain_input_mappings()
    domain_config = _domain_config(mapping_config, domain_name)
    frame = _validated_or_empty(normalized_df)
    rows: list[dict[str, Any]] = []
    for mapped_field, field_config in _domain_mappings(domain_config).items():
        candidate_series = list(field_config.get("candidate_series") or [])
        matched_series = _first_matching_series(frame, candidate_series)
        matched_meta = _matched_metadata(frame, matched_series)
        is_available = matched_series is not None and _is_active_mapping(field_config)
        rows.append(
            {
                "domain_name": domain_name,
                "mapped_field": mapped_field,
                "candidate_series": candidate_series,
                "matched_series": matched_series if is_available else None,
                "is_available": is_available,
                "required": bool(field_config.get("required", False)),
                "missing_reason": _missing_reason(field_config, matched_series),
                "source_name": matched_meta.get("source_name") if is_available else field_config.get("source_name"),
                "source_type": matched_meta.get("source_type") if is_available else field_config.get("source_type"),
                "feature_role": field_config.get("feature_role"),
                "status": field_config.get("status"),
                "caveat": field_config.get("caveat"),
                "wti_m1_m2_m3_blocker_status": field_config.get("wti_m1_m2_m3_blocker_status"),
            }
        )
    return rows


def build_all_domain_input_coverage(
    normalized_df: pd.DataFrame,
    mappings: dict[str, Any] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    mapping_config = mappings or load_domain_input_mappings()
    return {
        domain_name: build_domain_input_coverage(normalized_df, domain_name, mappings=mapping_config)
        for domain_name in mapping_config
    }


def _default_mapping_path() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "domain_input_mappings.yaml"


def _domain_config(mappings: dict[str, Any], domain_name: str) -> dict[str, Any]:
    if domain_name not in mappings:
        raise KeyError(f"Unknown domain input mapping: {domain_name}")
    domain_config = mappings[domain_name]
    if not isinstance(domain_config, dict):
        raise ValueError(f"Domain input mapping must be a mapping: {domain_name}")
    return domain_config


def _domain_mappings(domain_config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mappings = domain_config.get("mappings") or {}
    if not isinstance(mappings, dict):
        raise ValueError("Domain mappings must be a mapping.")
    return mappings


def _validated_or_empty(normalized_df: pd.DataFrame) -> pd.DataFrame:
    if normalized_df.empty:
        return normalized_df.copy()
    return validate_macro_series_frame(normalized_df)


def _date_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "date" not in frame.columns:
        return pd.DataFrame(columns=["date"])
    return pd.DataFrame({"date": sorted(frame["date"].dropna().unique())})


def _is_active_mapping(field_config: dict[str, Any]) -> bool:
    status = field_config.get("status")
    if status in TODO_STATUSES:
        return False
    return bool(field_config.get("candidate_series"))


def _first_matching_series(frame: pd.DataFrame, candidate_series: list[str]) -> str | None:
    if frame.empty or "series_id" not in frame.columns:
        return None
    available = set(frame["series_id"].dropna().astype(str))
    for series_id in candidate_series:
        if str(series_id) in available:
            return str(series_id)
    return None


def _matched_metadata(frame: pd.DataFrame, matched_series: str | None) -> dict[str, Any]:
    if matched_series is None or frame.empty:
        return {}
    rows = frame.loc[frame["series_id"].astype(str).eq(matched_series)]
    if rows.empty:
        return {}
    first = rows.iloc[0]
    return {
        "source_name": first.get("source_name"),
        "source_type": first.get("source_type"),
    }


def _missing_reason(field_config: dict[str, Any], matched_series: str | None) -> str | None:
    if matched_series is not None and _is_active_mapping(field_config):
        return None
    if not field_config.get("candidate_series"):
        return "NO_CANDIDATE_SERIES"
    if field_config.get("status") in TODO_STATUSES:
        return str(field_config.get("status"))
    return "SERIES_NOT_FOUND"
