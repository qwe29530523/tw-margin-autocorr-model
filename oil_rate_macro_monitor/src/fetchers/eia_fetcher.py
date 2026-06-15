from __future__ import annotations

import time
import re
from typing import Iterable

import pandas as pd
import requests

from src.utils.logging import get_logger


DEFAULT_EIA_SERIES = [
    "WCESTUS1",
    "WGTSTUS1",
    "WDISTUS1",
    "WCRFPUS2",
    "WCRRIUS2",
    "WCREXUS2",
    "WGFUPUS2",
    "WDIUPUS2",
    "WKJUPUS2",
    "EMM_EPMR_PTE_NUS_DPG",
    "EMD_EPD2D_PTE_NUS_DPG",
    "EER_EPD2F_PF4_Y35NY_DPG",
    "PET.WPULEUS3.W",
]

EIA_SERIES_ID_ALIASES = {
    "WCESTUS1": "PET.WCESTUS1.W",
    "WGTSTUS1": "PET.WGTSTUS1.W",
    "WDISTUS1": "PET.WDISTUS1.W",
    "WCRFPUS2": "PET.WCRFPUS2.W",
    "WCRRIUS2": "PET.WCRRIUS2.W",
    "WCREXUS2": "PET.WCREXUS2.W",
    "WGFUPUS2": "PET.WGFUPUS2.W",
    "WDIUPUS2": "PET.WDIUPUS2.W",
    "WKJUPUS2": "PET.WKJUPUS2.W",
    "EMM_EPMR_PTE_NUS_DPG": "PET.EMM_EPMR_PTE_NUS_DPG.W",
    "EMD_EPD2D_PTE_NUS_DPG": "PET.EMD_EPD2D_PTE_NUS_DPG.W",
    "EER_EPD2F_PF4_Y35NY_DPG": "PET.EER_EPD2F_PF4_Y35NY_DPG.W",
}

logger = get_logger(__name__)


def empty_eia_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=["date", "value", "series_id", "units"])


def fetch_eia_series(
    series_id: str,
    start: str | None = None,
    end: str | None = None,
    api_key: str | None = None,
    retries: int = 3,
) -> pd.DataFrame:
    if not api_key:
        logger.warning("Skipping EIA series %s because EIA_API_KEY is missing.", series_id)
        return empty_eia_frame()

    api_series_id = EIA_SERIES_ID_ALIASES.get(series_id, series_id)
    url = f"https://api.eia.gov/v2/seriesid/{api_series_id}"
    params: dict[str, str] = {"api_key": api_key}
    if start:
        params["start"] = start
    if end:
        params["end"] = end

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            payload = response.json()
            rows = payload.get("response", {}).get("data", [])
            df = pd.DataFrame(rows)
            if df.empty:
                return empty_eia_frame()
            date_col = "period" if "period" in df.columns else "date"
            units = df["units"] if "units" in df.columns else pd.NA
            out = pd.DataFrame(
                {
                    "date": pd.to_datetime(df[date_col], errors="coerce"),
                    "value": pd.to_numeric(df["value"], errors="coerce"),
                    "series_id": series_id,
                    "units": units,
                }
            )
            return out.dropna(subset=["date"])
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "EIA fetch failed for %s attempt %s/%s: %s",
                series_id,
                attempt,
                retries,
                redact_api_key(str(exc)),
            )
            if attempt < retries:
                time.sleep(1.0 * attempt)
    return empty_eia_frame()


def redact_api_key(text: str) -> str:
    return re.sub(r"api_key=[^&\\s]+", "api_key=<redacted>", text)


def fetch_many_eia_series(
    series_ids: Iterable[str] = DEFAULT_EIA_SERIES,
    start: str | None = None,
    end: str | None = None,
    api_key: str | None = None,
) -> pd.DataFrame:
    frames = [fetch_eia_series(series_id, start, end, api_key) for series_id in series_ids]
    if not frames:
        return empty_eia_frame()
    return pd.concat(frames, ignore_index=True)
