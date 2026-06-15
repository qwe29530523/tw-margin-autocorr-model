from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any


OIL_INFLATION_ENV_VAR = "OIL_INFLATION_SYSTEM_ROOT"
SOURCE_PATTERNS = (
    "data/reports/*.json",
    "data/reports/*.md",
    "reports/*.json",
    "reports/*.md",
    "data/processed/*.json",
    "data/processed/*.csv",
    "processed/*.json",
    "processed/*.csv",
    "output/*.json",
    "output/*.csv",
)


def _repo_root(repo_root: str | Path | None = None) -> Path:
    if repo_root is not None:
        return Path(repo_root)
    return Path(__file__).resolve().parents[3]


def _system_root(repo_root: str | Path | None = None, system_root: str | Path | None = None) -> Path:
    if system_root is not None:
        return Path(system_root)
    env_root = os.getenv(OIL_INFLATION_ENV_VAR)
    if env_root:
        return Path(env_root)
    return _repo_root(repo_root) / "oil_rate_macro_monitor"


def _newest_candidate(system_root: Path) -> Path | None:
    candidates: list[Path] = []
    for pattern in SOURCE_PATTERNS:
        candidates.extend(
            path
            for path in system_root.glob(pattern)
            if path.is_file() and path.name != ".gitkeep"
        )
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _read_csv_summary(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {
        "row_count": len(rows),
        "latest_row": rows[-1] if rows else {},
    }


def _read_markdown_summary(path: Path) -> dict[str, Any]:
    content = path.read_text(encoding="utf-8")
    return {
        "format": "markdown",
        "text": content,
    }


def load_oil_rate_summary(
    repo_root: str | Path | None = None,
    system_root: str | Path | None = None,
) -> dict[str, Any]:
    oil_root = _system_root(repo_root, system_root)
    result: dict[str, Any] = {
        "layer": "Global Macro Layer",
        "schema_key": "global_oil_inflation_pressure",
        "system": "oil_rate_macro_monitor",
        "system_root": str(oil_root),
        "source_path": "",
        "status": "MISSING",
        "data": {},
    }

    if not oil_root.exists():
        result["message"] = "Oil + inflation system root is missing."
        return result

    source_path = _newest_candidate(oil_root)
    if source_path is None:
        result["message"] = "No oil + inflation report or processed data file was found."
        return result

    result["source_path"] = str(source_path)
    try:
        suffix = source_path.suffix.lower()
        if suffix == ".json":
            with source_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        elif suffix == ".csv":
            payload = _read_csv_summary(source_path)
        elif suffix == ".md":
            payload = _read_markdown_summary(source_path)
        else:
            result["status"] = "ERROR"
            result["message"] = f"Unsupported oil + inflation source file type: {source_path.suffix}"
            return result
    except Exception as exc:
        result["status"] = "ERROR"
        result["message"] = f"Failed to read oil + inflation source file: {exc}"
        return result

    result["status"] = "OK"
    result["data"] = payload
    return result
