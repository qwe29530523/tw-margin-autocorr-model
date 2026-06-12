from __future__ import annotations

from pathlib import Path

from src.common.io import ensure_dir, write_json


def run_cpi_nowcast_backtest(start: str, end: str, output_dir: Path) -> dict:
    result = {
        "system": "rates_cpi",
        "backtest": "cpi_nowcast",
        "start": start,
        "end": end,
        "status": "mock_only",
        "point_in_time_real_data": False,
        "mae": None,
        "rmse": None,
        "bias": None,
        "warnings": ["Backtest is scaffolded until point-in-time CPI vintages are wired."],
    }
    write_json(ensure_dir(output_dir) / "cpi_nowcast_backtest.json", result)
    return result
