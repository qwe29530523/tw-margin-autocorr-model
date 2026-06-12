from __future__ import annotations

import pandas as pd

from src.systems.rates_cpi.fetchers.bls_fetcher import BLS_CPI_SERIES
from src.systems.rates_cpi.fetchers.fred_fetcher import FRED_RATES_SERIES


def validate_fred_rates_frame(frame: pd.DataFrame, source_mode: str) -> dict:
    warnings: list[str] = []
    if source_mode != "real":
        warnings.append("FRED source mode is not real API data.")
    if frame.empty:
        warnings.append("FRED rates frame is empty.")
    elif not {"date", "series", "value"}.issubset(frame.columns):
        warnings.append("FRED rates frame missing required columns.")
    else:
        present = set(frame["series"].dropna())
        for series_id in FRED_RATES_SERIES:
            if series_id not in present:
                warnings.append(f"FRED rates series missing: {series_id}.")
        dates = pd.to_datetime(frame["date"], errors="coerce").dropna()
        if len(dates) < 10:
            warnings.append("FRED rates frame has too few dated observations.")
    return {"source": "fred", "real_data": source_mode == "real" and not warnings, "warnings": warnings}


def validate_bls_components(components: dict, source_mode: str) -> dict:
    warnings: list[str] = []
    if source_mode != "real":
        warnings.append("BLS source mode is not real API data.")
    for key in BLS_CPI_SERIES:
        if key not in components:
            warnings.append(f"BLS CPI component missing: {key}.")
    if not components.get("cpi_asof_month"):
        warnings.append("BLS CPI as-of month missing.")
    return {"source": "bls", "real_data": source_mode == "real" and not warnings, "warnings": warnings}
