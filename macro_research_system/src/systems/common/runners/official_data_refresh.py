from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.systems.common.api_key_preflight import run_api_key_preflight


CONFIG_FILES_BY_SOURCE = {
    "FRED": "fred_official_series.yaml",
    "BLS": "bls_official_series.yaml",
    "EIA": "eia_official_series.yaml",
    "Census": "census_official_series.yaml",
    "MetalPriceAPI": "energy_benchmark_research_sources.yaml",
}

REFRESH_MODE = "dry_run"


def build_official_source_diagnostics(repo_root: str | Path | None = None) -> list[dict[str, Any]]:
    root = Path(repo_root) if repo_root is not None else _default_repo_root()
    registry = _load_yaml(root / "macro_research_system" / "config" / "api_source_registry.yaml")
    preflight_by_name = {
        row["source_name"]: row
        for row in run_api_key_preflight(repo_root=root)
    }

    diagnostics: list[dict[str, Any]] = []
    for source_key, source_config in registry.items():
        source_name = str(source_config.get("source_name") or source_key)
        source_type = source_config.get("source_type")
        blocker_status = source_config.get("blocker_status")
        research_only = str(source_type).startswith("research_only")
        preflight = preflight_by_name.get(source_name, {})
        active_series_count = _active_series_count(root, source_name)
        todo_verify_count = _todo_verify_count(root, source_name)
        planned_for_refresh, excluded_reason = _diagnostic_refresh_status(
            is_configured=bool(preflight.get("is_configured")),
            blocker_status=blocker_status,
            active_series_count=active_series_count,
            research_only=research_only,
        )

        diagnostics.append(
            {
                "source_name": source_name,
                "source_type": source_type,
                "is_configured": bool(preflight.get("is_configured")),
                "blocker_status": blocker_status,
                "active_series_count": active_series_count,
                "todo_verify_count": todo_verify_count,
                "planned_for_refresh": planned_for_refresh,
                "excluded_reason": excluded_reason,
                "research_only": research_only,
                "usable_for": source_config.get("usable_for") or [],
                "not_usable_for": source_config.get("not_usable_for") or [],
            }
        )
    return diagnostics


def build_refresh_plan(include_research_only: bool = False, repo_root: str | Path | None = None) -> list[dict[str, Any]]:
    root = Path(repo_root) if repo_root is not None else _default_repo_root()
    diagnostics_by_name = {
        row["source_name"]: row
        for row in build_official_source_diagnostics(repo_root=root)
    }

    plan: list[dict[str, Any]] = []
    for source_name, diagnostic in diagnostics_by_name.items():
        if diagnostic["blocker_status"] == "open":
            continue
        if diagnostic["research_only"] and not include_research_only:
            continue
        if not diagnostic["is_configured"]:
            continue
        plan.extend(_plan_entries_for_source(root, source_name, diagnostic))
    return plan


def run_official_data_refresh_dry_run(
    include_research_only: bool = False,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    diagnostics = build_official_source_diagnostics(repo_root=repo_root)
    refresh_plan = build_refresh_plan(include_research_only=include_research_only, repo_root=repo_root)
    return {
        "mode": REFRESH_MODE,
        "include_research_only": include_research_only,
        "network_calls": 0,
        "files_written": 0,
        "diagnostics": diagnostics,
        "summary": summarize_refresh_diagnostics(diagnostics),
        "refresh_plan": refresh_plan,
    }


def summarize_refresh_diagnostics(diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    census = _first_source(diagnostics, "Census")
    cme = _first_source(diagnostics, "CME DataMine")
    return {
        "source_count": len(diagnostics),
        "official_planned_source_count": sum(
            1
            for row in diagnostics
            if row["planned_for_refresh"] and not row["research_only"]
        ),
        "research_only_source_count": sum(1 for row in diagnostics if row["research_only"]),
        "blocked_source_count": sum(1 for row in diagnostics if row.get("blocker_status") == "open"),
        "wti_m1_m2_m3_blocker_status": cme.get("blocker_status") if cme else None,
        "census_active_series_count": census.get("active_series_count", 0) if census else 0,
    }


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _load_yaml(path: Path) -> Any:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _config_path(root: Path, source_name: str) -> Path:
    file_name = CONFIG_FILES_BY_SOURCE.get(source_name)
    if not file_name:
        return root / "macro_research_system" / "config" / "__missing__.yaml"
    return root / "macro_research_system" / "config" / file_name


def _active_series_count(root: Path, source_name: str) -> int:
    if source_name == "MetalPriceAPI":
        payload = _load_yaml(_config_path(root, source_name))
        return len(payload.get("symbols") or [])
    return len(_active_series_entries(root, source_name))


def _todo_verify_count(root: Path, source_name: str) -> int:
    payload = _load_yaml(_config_path(root, source_name))
    todo = payload.get("todo_verify") if isinstance(payload, dict) else None
    return len(_flatten_todo_entries(todo))


def _diagnostic_refresh_status(
    is_configured: bool,
    blocker_status: str | None,
    active_series_count: int,
    research_only: bool,
) -> tuple[bool, str | None]:
    if blocker_status == "open":
        return False, "BLOCKER_OPEN"
    if research_only:
        return False, "RESEARCH_ONLY_EXCLUDED"
    if not is_configured:
        return False, "MISSING_ENV"
    if active_series_count <= 0:
        return False, "NO_ACTIVE_SERIES"
    return True, None


def _plan_entries_for_source(root: Path, source_name: str, diagnostic: dict[str, Any]) -> list[dict[str, Any]]:
    if source_name == "MetalPriceAPI":
        return _metalprice_plan_entries(root, diagnostic)
    return [
        _official_plan_entry(source_name, diagnostic, entry)
        for entry in _active_series_entries(root, source_name)
    ]


def _official_plan_entry(source_name: str, diagnostic: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_name": source_name,
        "source_type": diagnostic["source_type"],
        "series_id": str(entry.get("series_id")),
        "series_name": str(entry.get("series_name") or entry.get("series_id")),
        "group": entry.get("group"),
        "feature_role": entry.get("feature_role"),
        "active": True,
        "research_only": False,
        "refresh_mode": REFRESH_MODE,
        "not_usable_for": entry.get("not_usable_for") or diagnostic.get("not_usable_for") or [],
    }


def _metalprice_plan_entries(root: Path, diagnostic: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _load_yaml(_config_path(root, "MetalPriceAPI"))
    symbols = payload.get("symbols") or []
    not_usable_for = payload.get("not_usable_for") or diagnostic.get("not_usable_for") or []
    return [
        {
            "source_name": "MetalPriceAPI",
            "source_type": diagnostic["source_type"],
            "series_id": str(symbol),
            "series_name": f"MetalPriceAPI {symbol} benchmark",
            "group": "energy_benchmark_research",
            "feature_role": str(symbol).lower(),
            "active": True,
            "research_only": True,
            "refresh_mode": REFRESH_MODE,
            "not_usable_for": not_usable_for,
        }
        for symbol in symbols
    ]


def _active_series_entries(root: Path, source_name: str) -> list[dict[str, Any]]:
    payload = _load_yaml(_config_path(root, source_name))
    if not isinstance(payload, dict):
        return []

    active_entries: list[dict[str, Any]] = []
    for group, entries in payload.items():
        if group == "todo_verify" or not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if entry.get("series_id") == "TODO_VERIFY":
                continue
            if entry.get("active", True) is not True:
                continue
            row = dict(entry)
            row.setdefault("group", group)
            active_entries.append(row)
    return active_entries


def _flatten_todo_entries(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        entries: list[dict[str, Any]] = []
        for value in payload.values():
            if isinstance(value, dict) and value.get("series_id") == "TODO_VERIFY":
                entries.append(value)
            else:
                entries.extend(_flatten_todo_entries(value))
        return entries
    return []


def _first_source(diagnostics: list[dict[str, Any]], source_name: str) -> dict[str, Any] | None:
    for row in diagnostics:
        if row["source_name"] == source_name:
            return row
    return None
