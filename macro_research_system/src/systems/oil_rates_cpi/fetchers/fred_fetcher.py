from __future__ import annotations

import json
import urllib.parse
import urllib.request

import pandas as pd

from src.common.settings import Settings


FRED_SERIES = [
    "FEDFUNDS",
    "SOFR",
    "DGS3MO",
    "DGS1",
    "DGS2",
    "DGS5",
    "DGS10",
    "DGS30",
    "T10Y2Y",
    "T10Y3M",
    "DCOILWTICO",
    "DCOILBRENTEU",
]


def _observations_to_frame(payload: dict, series_id: str) -> pd.DataFrame:
    rows = []
    for item in payload.get("observations", []):
        value = item.get("value")
        if value in {None, ".", "", "NaN"}:
            continue
        rows.append({"date": item.get("date"), "series": series_id, "value": float(value)})
    return pd.DataFrame(rows)


def _fetch_fred_observations(api_key: str, series_id: str) -> pd.DataFrame:
    params = urllib.parse.urlencode(
        {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": "2018-01-01",
        }
    )
    url = f"https://api.stlouisfed.org/fred/series/observations?{params}"
    with urllib.request.urlopen(url, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return _observations_to_frame(payload, series_id)


def fetch_fred_series(settings: Settings) -> tuple[pd.DataFrame, list[str]]:
    warnings: list[str] = []
    if settings.mock_mode or not settings.fred_api_key:
        warnings.append("FRED mock data used; FRED_API_KEY missing or MOCK_MODE=true.")
        rows = [
            ("2026-05-01", "FEDFUNDS", 3.90),
            ("2026-05-01", "SOFR", 4.00),
            ("2026-05-01", "DGS3MO", 3.70),
            ("2026-05-01", "DGS1", 3.75),
            ("2026-05-01", "DGS2", 3.80),
            ("2026-05-01", "DGS5", 3.90),
            ("2026-05-01", "DGS10", 4.00),
            ("2026-05-01", "DGS30", 4.50),
            ("2026-06-04", "FEDFUNDS", 3.63),
            ("2026-06-04", "SOFR", 3.62),
            ("2026-06-04", "DGS3MO", 3.78),
            ("2026-06-04", "DGS1", 3.82),
            ("2026-06-04", "DGS2", 4.05),
            ("2026-06-04", "DGS5", 4.18),
            ("2026-06-04", "DGS10", 4.47),
            ("2026-06-04", "DGS30", 4.97),
            ("2026-06-05", "T10Y2Y", 0.38),
            ("2026-06-05", "T10Y3M", 0.77),
            ("2026-06-01", "DCOILWTICO", 95.96),
            ("2026-06-01", "DCOILBRENTEU", 98.29),
        ]
        return pd.DataFrame(rows, columns=["date", "series", "value"]), warnings
    try:
        frames = [_fetch_fred_observations(settings.fred_api_key, series_id) for series_id in FRED_SERIES]
        result = pd.concat([frame for frame in frames if not frame.empty], ignore_index=True)
        if result.empty:
            raise RuntimeError("FRED API returned no observations")
        return result, warnings
    except Exception as exc:
        warnings.append(f"FRED real-data fetch failed; using mock data. Reason: {type(exc).__name__}.")
        mock_settings = type(settings)(
            fred_api_key=None,
            eia_api_key=settings.eia_api_key,
            bls_api_key=settings.bls_api_key,
            use_yahoo=settings.use_yahoo,
            mock_mode=True,
        )
        return fetch_fred_series(mock_settings)
