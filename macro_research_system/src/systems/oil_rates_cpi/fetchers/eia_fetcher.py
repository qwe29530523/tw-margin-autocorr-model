from __future__ import annotations

from src.common.settings import Settings
from src.systems.oil_market.fetchers.eia_fetcher import fetch_eia_oil_frame


def fetch_eia_series(settings: Settings) -> tuple[pd.DataFrame, list[str]]:
    frame, warnings, source_mode = fetch_eia_oil_frame(settings)
    if source_mode != "real":
        warnings.append("Oil/Rates/CPI EIA data is not real API data.")
    return frame, warnings
