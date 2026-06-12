from __future__ import annotations

from pathlib import Path

from src.common.io import write_json
def run_cpi_nowcast_backtest(mock_mode: bool = True, start: str = "2018-01", end: str = "2026-05", output_dir: Path | None = None) -> dict:
    result = {
        "system": "cpi_nowcast_backtest",
        "status": "mock_only" if mock_mode else "disabled",
        "start": start,
        "end": end,
        "mae": None,
        "rmse": None,
        "bias": None,
        "direction_hit_rate": None,
        "within_0_1pp_hit_rate": None,
        "warnings": ["Backtest disabled/mock_only; point-in-time real CPI data not wired yet."],
    }
    if output_dir is not None:
        write_json(output_dir / "cpi_nowcast_backtest.json", result)
    return result
