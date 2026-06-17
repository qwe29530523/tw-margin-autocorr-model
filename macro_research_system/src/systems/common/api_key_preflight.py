from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


SAFE_FIELDS = [
    "source_name",
    "source_type",
    "primary_env",
    "is_configured",
    "configured_by",
    "missing_reason",
    "blocker_status",
]


def run_api_key_preflight(
    repo_root: str | Path | None = None,
    registry_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    root = Path(repo_root) if repo_root is not None else _default_repo_root()
    _load_root_dotenv(root)
    registry = _load_registry(Path(registry_path) if registry_path is not None else _default_registry_path(root))
    return [_source_status(source_key, source_config) for source_key, source_config in registry.items()]


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _default_registry_path(repo_root: Path) -> Path:
    return repo_root / "macro_research_system" / "config" / "api_source_registry.yaml"


def _load_root_dotenv(repo_root: Path) -> None:
    dotenv_path = repo_root / ".env"
    if not dotenv_path.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(dotenv_path=dotenv_path, override=False)
    except ImportError:
        _load_dotenv_fallback(dotenv_path)


def _load_dotenv_fallback(dotenv_path: Path) -> None:
    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _load_registry(registry_path: Path) -> dict[str, dict[str, Any]]:
    with registry_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError("API source registry must be a mapping.")
    return payload


def _source_status(source_key: str, source_config: dict[str, Any]) -> dict[str, Any]:
    source_name = str(source_config.get("source_name") or source_key)
    source_type = source_config.get("source_type")
    primary_env = source_config.get("api_key_env")
    blocker_status = source_config.get("blocker_status")

    if primary_env is None:
        return _safe_status(
            source_name=source_name,
            source_type=source_type,
            primary_env=None,
            is_configured=False,
            configured_by=None,
            missing_reason=_pending_reason(source_config),
            blocker_status=blocker_status,
        )

    primary_env = str(primary_env)
    is_configured = bool(os.getenv(primary_env))
    return _safe_status(
        source_name=source_name,
        source_type=source_type,
        primary_env=primary_env,
        is_configured=is_configured,
        configured_by=primary_env if is_configured else None,
        missing_reason=None if is_configured else "MISSING_ENV",
        blocker_status=blocker_status,
    )


def _pending_reason(source_config: dict[str, Any]) -> str | None:
    status = source_config.get("status")
    if status == "pending_vendor_or_licensed_delivery":
        return "PENDING_VENDOR_OR_LICENSED_DELIVERY"
    return None


def _safe_status(
    source_name: str,
    source_type: str | None,
    primary_env: str | None,
    is_configured: bool,
    configured_by: str | None,
    missing_reason: str | None,
    blocker_status: str | None,
) -> dict[str, Any]:
    return {
        "source_name": source_name,
        "source_type": source_type,
        "primary_env": primary_env,
        "is_configured": is_configured,
        "configured_by": configured_by,
        "missing_reason": missing_reason,
        "blocker_status": blocker_status,
    }
