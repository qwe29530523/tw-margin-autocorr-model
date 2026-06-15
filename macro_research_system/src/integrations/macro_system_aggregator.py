from __future__ import annotations

"""Upper-level aggregator for independent macro system outputs.

The aggregator reads adapter summaries for Taiwan local liquidity and global
oil / inflation pressure, then writes ``macro_system_summary.json``. It does
not move data folders, merge model internals, or recompute any subsystem.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

try:
    from .oil_rate_adapter import load_oil_rate_summary
    from .tw_margin_adapter import load_tw_margin_summary
except ImportError:  # pragma: no cover - supports direct script execution
    from oil_rate_adapter import load_oil_rate_summary
    from tw_margin_adapter import load_tw_margin_summary


def _repo_root(repo_root: str | Path | None = None) -> Path:
    if repo_root is not None:
        return Path(repo_root)
    return Path(__file__).resolve().parents[3]


def _aggregate_status(statuses: list[str]) -> str:
    if all(status == "OK" for status in statuses):
        return "OK"
    if all(status == "MISSING" for status in statuses):
        return "MISSING"
    if any(status == "ERROR" for status in statuses):
        return "ERROR"
    return "PARTIAL"


def _final_macro_risk_gate(tw_margin: dict[str, Any], oil_rate: dict[str, Any]) -> dict[str, Any]:
    input_statuses = {
        "taiwan_local_liquidity": tw_margin["status"],
        "global_oil_inflation_pressure": oil_rate["status"],
    }
    status = _aggregate_status(list(input_statuses.values()))
    if status == "OK":
        message = "All subsystem summaries are available; no model recomputation was performed."
    elif status == "MISSING":
        message = "All subsystem summaries are missing; final macro risk gate is unavailable."
    elif status == "ERROR":
        message = "At least one subsystem adapter returned ERROR; final macro risk gate is unavailable."
    else:
        message = "Some subsystem summaries are unavailable; final macro risk gate is partial."
    return {
        "status": status,
        "input_statuses": input_statuses,
        "message": message,
    }


def build_macro_system_summary(
    repo_root: str | Path | None = None,
    output_path: str | Path | None = None,
    write: bool = True,
) -> dict[str, Any]:
    root = _repo_root(repo_root)
    tw_margin = load_tw_margin_summary(repo_root=root)
    oil_rate = load_oil_rate_summary(repo_root=root)
    final_macro_risk_gate = _final_macro_risk_gate(tw_margin, oil_rate)
    summary: dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": final_macro_risk_gate["status"],
        "taiwan_local_liquidity": tw_margin,
        "global_oil_inflation_pressure": oil_rate,
        "final_macro_risk_gate": final_macro_risk_gate,
    }

    if write:
        destination = (
            Path(output_path)
            if output_path is not None
            else root / "macro_research_system" / "data" / "outputs" / "macro_system_summary.json"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8") as handle:
            json.dump(summary, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        summary["output_path"] = str(destination)

    return summary


def main() -> None:
    summary = build_macro_system_summary()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
