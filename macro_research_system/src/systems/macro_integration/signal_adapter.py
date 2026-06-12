from __future__ import annotations

from pathlib import Path

from src.common.io import read_json


def load_system_summaries(data_root: Path) -> tuple[dict, dict, dict, list[str]]:
    warnings: list[str] = []
    tw_path = data_root / "tw_margin_cycle" / "processed" / "tw_margin_cycle_summary.json"
    oil_path = data_root / "oil_market" / "processed" / "oil_market_summary.json"
    rates_path = data_root / "rates_cpi" / "processed" / "rates_cpi_summary.json"
    if tw_path.exists():
        tw = read_json(tw_path)
    else:
        tw = {}
        warnings.append("System A TW margin summary missing; using empty fallback.")
    if oil_path.exists():
        oil = read_json(oil_path)
    else:
        oil = {}
        warnings.append("System B oil_market summary missing; using empty fallback.")
    if rates_path.exists():
        rates = read_json(rates_path)
    else:
        rates = {}
        warnings.append("Rates x CPI summary missing; using empty fallback.")
    return tw, oil, rates, warnings
