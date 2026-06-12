from __future__ import annotations

import json
import urllib.parse
import urllib.request

import pandas as pd

from src.common.dates import today_taipei
from src.common.settings import Settings


FRED_SERIES = {"DCOILWTICO": "wti", "DCOILBRENTEU": "brent"}


def _mock_oil_prices() -> pd.DataFrame:
    dates = pd.date_range(end=pd.Timestamp(today_taipei()), periods=320, freq="B")
    rows = []
    for index, date in enumerate(dates):
        cycle = (index % 80) / 80
        wti = 76 + index * 0.035 + 6 * (cycle - 0.5)
        brent = wti + 3.0
        rows.append({"date": date, "wti": round(wti, 2), "brent": round(brent, 2)})
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
    rows = []
    for item in payload.get("observations", []):
        value = item.get("value")
        if value in {None, "."}:
            continue
        rows.append({"date": item["date"], "value": float(value)})
    return pd.DataFrame(rows)


def fetch_oil_price_frame(settings: Settings) -> tuple[pd.DataFrame, list[str], str]:
    warnings: list[str] = []
    if settings.mock_mode or not settings.fred_api_key:
        warnings.append("FRED mock data used for oil prices; FRED_API_KEY missing or MOCK_MODE=true.")
        return _mock_oil_prices(), warnings, "mock"
    try:
        frames = []
        for series_id, column in FRED_SERIES.items():
            data = _fetch_fred_observations(settings.fred_api_key, series_id)
            if not data.empty:
                frames.append(data.rename(columns={"value": column}))
        if len(frames) != len(FRED_SERIES):
            raise RuntimeError("one or more FRED oil price series returned no data")
        merged = frames[0]
        for frame in frames[1:]:
            merged = merged.merge(frame, on="date", how="outer")
        merged["date"] = pd.to_datetime(merged["date"])
        merged = merged.sort_values("date").ffill().dropna(subset=["wti", "brent"])
        return merged, warnings, "real"
    except Exception as exc:
        warnings.append(f"FRED oil price fetch failed; using mock data. Reason: {type(exc).__name__}.")
        return _mock_oil_prices(), warnings, "fallback_mock"
