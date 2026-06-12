from __future__ import annotations

from pathlib import Path

from src.common.io import write_json


def run_macro_regime_backtest(start: str, end: str, output_dir: Path | None = None) -> dict:
    result = {
        "system": "macro_regime_backtest",
        "status": "mock_only",
        "start": start,
        "end": end,
        "forward_returns": None,
        "warnings": ["Backtest disabled/mock_only; point-in-time real market data not wired yet."],
    }
    if output_dir is not None:
        write_json(output_dir / "macro_regime_backtest.json", result)
    return result
