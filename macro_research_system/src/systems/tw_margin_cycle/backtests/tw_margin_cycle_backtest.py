from __future__ import annotations

from pathlib import Path

from src.common.io import write_json


def run_tw_margin_cycle_backtest(start: str, end: str, output_dir: Path | None = None) -> dict:
    result = {
        "system": "tw_margin_cycle_backtest",
        "status": "mock_only",
        "start": start,
        "end": end,
        "late_cycle_forward_returns": None,
        "deleveraging_risk_forward_drawdown": None,
        "margin_extreme_volatility_lift": None,
        "warnings": ["Backtest disabled/mock_only; point-in-time real data not wired yet."],
    }
    if output_dir is not None:
        write_json(output_dir / "tw_margin_cycle_backtest.json", result)
    return result
