from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_quality_flags(input_dir: Path) -> tuple[bool, bool, list[str]]:
    warnings: list[str] = []
    quality_path = input_dir / "data_quality_report.csv"
    extreme_path = input_dir / "market_extreme_report.csv"
    data_quality_warning = quality_path.exists() and len(pd.read_csv(quality_path)) > 0
    market_extreme_warning = extreme_path.exists() and len(pd.read_csv(extreme_path)) > 0
    if data_quality_warning:
        warnings.append("data_quality_report contains rows.")
    if market_extreme_warning:
        warnings.append("market_extreme_report contains rows.")
    return data_quality_warning, market_extreme_warning, warnings
