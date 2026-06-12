from __future__ import annotations

import pandas as pd

from src.common.settings import Settings


def fetch_optional_market_overlays(settings: Settings) -> tuple[pd.DataFrame, list[str]]:
    if not settings.use_yahoo:
        return pd.DataFrame(), ["USE_YAHOO=false; oil market overlay fetch skipped."]
    return pd.DataFrame(), ["Optional market overlays are not enabled in this first oil_market version."]
