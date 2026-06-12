from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_outlier_context(input_dir: Path) -> pd.DataFrame:
    path = input_dir / "outlier_context.csv"
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()
