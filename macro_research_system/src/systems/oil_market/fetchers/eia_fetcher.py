from __future__ import annotations

import json
import urllib.parse
import urllib.request

import pandas as pd

from src.common.dates import today_taipei
from src.common.settings import Settings


EIA_LEGACY_SERIES = {
    "PET.WCESTUS1.W": "crude_inventory",
    "PET.WGTSTUS1.W": "gasoline_inventory",
    "PET.WDISTUS1.W": "distillate_inventory",
    "PET.WPULEUS3.W": "refinery_utilization",
    "PET.WCRRIUS2.W": "refinery_crude_inputs",
    "PET.WCRFPUS2.W": "crude_production",
    "PET.WCREXUS2.W": "crude_exports",
    "PET.WGFUPUS2.W": "gasoline_product_supplied",
    "PET.WDIUPUS2.W": "distillate_product_supplied",
    "PET.WKJUPUS2.W": "jet_fuel_product_supplied",
}

EIA_SPOT_SERIES = {
    "RWTC": "wti_spot_price",
    "EER_EPMRU_PF4_RGC_DPG": "gasoline_spot_price",
    "EER_EPD2DXL0_PF4_RGC_DPG": "diesel_spot_price",
}


def _mock_eia_weekly() -> pd.DataFrame:
    dates = pd.date_range(end=pd.Timestamp(today_taipei()), periods=104, freq="W-FRI")
    rows = []
    for index, date in enumerate(dates):
        rows.append(
            {
                "date": date,
                "crude_inventory": 430000 - index * 180 + (index % 8) * 900,
                "gasoline_inventory": 225000 + (index % 10) * 320 - index * 35,
                "distillate_inventory": 123000 + (index % 7) * 260 - index * 20,
                "refinery_utilization": 88 + (index % 12) * 0.55,
                "refinery_crude_inputs": 15800 + index * 9 + (index % 5) * 60,
                "crude_production": 12600 + index * 8,
                "crude_exports": 3800 + (index % 14) * 120 + index * 4,
                "gasoline_product_supplied": 8900 + (index % 9) * 35,
                "distillate_product_supplied": 4050 + (index % 8) * 24,
                "jet_fuel_product_supplied": 1550 + (index % 10) * 15,
                "gasoline_crack_proxy": 18 + (index % 40) * 0.28,
                "diesel_crack_proxy": 24 + (index % 35) * 0.32,
            }
        )
    return pd.DataFrame(rows)


def _fetch_legacy_series(api_key: str, series_id: str) -> pd.DataFrame:
    params = urllib.parse.urlencode(
        {
            "api_key": api_key,
            "length": 5000,
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
        }
    )
    url = f"https://api.eia.gov/v2/seriesid/{series_id}?{params}"
    with urllib.request.urlopen(url, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    data = payload.get("response", {}).get("data", [])
    rows = []
    for item in data:
        period = item.get("period")
        value = item.get("value")
        if value in {None, "", "-", "--", "NA", "W"}:
            continue
        rows.append({"date": period, "value": float(value)})
    return pd.DataFrame(rows)


def _fetch_spot_series(api_key: str, series_id: str) -> pd.DataFrame:
    params = urllib.parse.urlencode(
        [
            ("api_key", api_key),
            ("frequency", "daily"),
            ("data[0]", "value"),
            ("facets[series][]", series_id),
            ("sort[0][column]", "period"),
            ("sort[0][direction]", "desc"),
            ("length", 5000),
        ]
    )
    url = f"https://api.eia.gov/v2/petroleum/pri/spt/data/?{params}"
    with urllib.request.urlopen(url, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    rows = []
    for item in payload.get("response", {}).get("data", []):
        value = item.get("value")
        if value in {None, "", "-", "--", "NA", "W"}:
            continue
        rows.append({"date": item.get("period"), "value": float(value)})
    return pd.DataFrame(rows)


def _fetch_spot_price_frame(api_key: str) -> pd.DataFrame:
    frames = []
    for series_id, column in EIA_SPOT_SERIES.items():
        data = _fetch_spot_series(api_key, series_id)
        if not data.empty:
            frames.append(data.rename(columns={"value": column}))
    if len(frames) != len(EIA_SPOT_SERIES):
        raise RuntimeError("one or more EIA spot price series returned no data")
    merged = frames[0]
    for frame in frames[1:]:
        merged = merged.merge(frame, on="date", how="outer")
    merged["date"] = pd.to_datetime(merged["date"])
    return merged.sort_values("date").ffill().dropna(subset=list(EIA_SPOT_SERIES.values()))


def _attach_crack_spread_proxy(weekly_frame: pd.DataFrame, spot_frame: pd.DataFrame) -> pd.DataFrame:
    result = weekly_frame.sort_values("date").copy()
    required = {"date", "wti_spot_price", "gasoline_spot_price", "diesel_spot_price"}
    if spot_frame.empty or not required.issubset(spot_frame.columns):
        result["gasoline_crack_proxy"] = pd.NA
        result["diesel_crack_proxy"] = pd.NA
        result["crack_spread_asof_date"] = pd.NA
        return result
    spot = spot_frame.sort_values("date").copy()
    spot["date"] = pd.to_datetime(spot["date"])
    spot = spot.rename(columns={"date": "spot_date"})
    result = pd.merge_asof(
        result,
        spot,
        left_on="date",
        right_on="spot_date",
        direction="backward",
        tolerance=pd.Timedelta(days=10),
    )
    wti = pd.to_numeric(result["wti_spot_price"], errors="coerce")
    gasoline = pd.to_numeric(result["gasoline_spot_price"], errors="coerce")
    diesel = pd.to_numeric(result["diesel_spot_price"], errors="coerce")
    result["gasoline_crack_proxy"] = (gasoline * 42 - wti).round(2)
    result["diesel_crack_proxy"] = (diesel * 42 - wti).round(2)
    result["crack_spread_asof_date"] = pd.to_datetime(result["spot_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return result.drop(columns=["spot_date"])


def fetch_eia_oil_frame(settings: Settings) -> tuple[pd.DataFrame, list[str], str]:
    warnings: list[str] = []
    if settings.mock_mode or not settings.eia_api_key:
        warnings.append("EIA mock data used for oil market; EIA_API_KEY missing or MOCK_MODE=true.")
        return _mock_eia_weekly(), warnings, "mock"
    try:
        frames = []
        for series_id, column in EIA_LEGACY_SERIES.items():
            data = _fetch_legacy_series(settings.eia_api_key, series_id)
            if not data.empty:
                frames.append(data.rename(columns={"value": column}))
        if len(frames) < 6:
            raise RuntimeError("too few EIA petroleum series returned data")
        merged = frames[0]
        for frame in frames[1:]:
            merged = merged.merge(frame, on="date", how="outer")
        merged["date"] = pd.to_datetime(merged["date"])
        merged = merged.sort_values("date").ffill()
        try:
            merged = _attach_crack_spread_proxy(merged, _fetch_spot_price_frame(settings.eia_api_key))
        except Exception as exc:
            warnings.append(f"EIA spot price fetch failed; crack spread proxy missing. Reason: {type(exc).__name__}.")
            merged = _attach_crack_spread_proxy(merged, pd.DataFrame())
        return merged, warnings, "real"
    except Exception as exc:
        warnings.append(f"EIA oil market fetch failed; using mock data. Reason: {type(exc).__name__}.")
        return _mock_eia_weekly(), warnings, "fallback_mock"
