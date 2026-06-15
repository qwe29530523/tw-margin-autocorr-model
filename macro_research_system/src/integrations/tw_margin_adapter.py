from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


TW_MARGIN_ENV_VAR = "TW_MARGIN_SYSTEM_ROOT"
SIGNAL_SUMMARY_RELATIVE_PATH = Path("output") / "signal_summary.json"


def _repo_root(repo_root: str | Path | None = None) -> Path:
    if repo_root is not None:
        return Path(repo_root)
    return Path(__file__).resolve().parents[3]


def _system_root(repo_root: str | Path | None = None, system_root: str | Path | None = None) -> Path:
    if system_root is not None:
        return Path(system_root)
    env_root = os.getenv(TW_MARGIN_ENV_VAR)
    if env_root:
        return Path(env_root)
    return _repo_root(repo_root)


def load_tw_margin_summary(
    repo_root: str | Path | None = None,
    system_root: str | Path | None = None,
) -> dict[str, Any]:
    tw_root = _system_root(repo_root, system_root)
    source_path = tw_root / SIGNAL_SUMMARY_RELATIVE_PATH
    result: dict[str, Any] = {
        "layer": "Taiwan Local Market Layer",
        "schema_key": "taiwan_local_liquidity",
        "system": "tw_margin_autocorr_model",
        "system_root": str(tw_root),
        "source_path": str(source_path),
        "status": "MISSING",
        "data": {},
    }

    if not source_path.exists():
        result["message"] = "TW margin signal summary file is missing."
        return result

    try:
        with source_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:
        result["status"] = "ERROR"
        result["message"] = f"Failed to read TW margin signal summary: {exc}"
        return result

    result["status"] = "OK"
    result["data"] = payload
    return result
