from __future__ import annotations

from pathlib import Path

from src.common.io import ensure_dir, write_json


def run_oil_regime_backtest(start: str, end: str, output_dir: Path, mock_mode: bool = True) -> dict:
    result = {
        "system": "oil_market",
        "backtest": "oil_regime_backtest",
        "start": start,
        "end": end,
        "status": "mock_only" if mock_mode else "disabled",
        "point_in_time_real_data": False,
        "targets": [
            "oil_regime_forward_wti_brent_20d_60d_120d_return",
            "inventory_tightening_forward_oil_return",
            "product_demand_softening_forward_oil_return",
            "tight_inventory_weak_products_volatility_or_drawdown",
        ],
        "results": {},
        "warnings": ["Backtest disabled for formal research until point-in-time real data is wired."],
    }
    write_json(ensure_dir(output_dir) / "oil_regime_backtest.json", result)
    return result
