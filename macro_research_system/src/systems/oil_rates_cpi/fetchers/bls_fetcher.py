from __future__ import annotations

import json
import urllib.request

from src.common.settings import Settings


BLS_CPI_SERIES = {
    "energy_proxy_mom": "CUUR0000SA0E",
    "gasoline_proxy_mom": "CUUR0000SETB01",
    "food_proxy_mom": "CUUR0000SAF1",
    "shelter_proxy_mom": "CUUR0000SAH1",
    "core_goods_proxy_mom": "CUUR0000SACL1E",
    "core_services_ex_shelter_proxy_mom": "CUUR0000SASLE",
}


def _series_to_mom(series: dict) -> tuple[float, str]:
    rows = [
        item
        for item in series.get("data", [])
        if str(item.get("period", "")).startswith("M") and item.get("period") != "M13"
    ]
    rows = sorted(rows, key=lambda item: (int(item["year"]), int(item["period"][1:])))
    if len(rows) < 2:
        raise ValueError("not enough monthly CPI observations")
    latest = rows[-1]
    previous = rows[-2]
    mom = float(latest["value"]) / float(previous["value"]) - 1
    asof = f"{latest['year']}-{latest['period'][1:]}"
    return mom, asof


def _fetch_bls_series(api_key: str) -> dict:
    payload = json.dumps(
        {
            "seriesid": list(BLS_CPI_SERIES.values()),
            "startyear": "2024",
            "endyear": "2026",
            "registrationkey": api_key,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.bls.gov/publicAPI/v2/timeseries/data/",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_bls_cpi(settings: Settings) -> tuple[dict, list[str]]:
    warnings: list[str] = []
    if settings.mock_mode or not settings.bls_api_key:
        warnings.append("BLS mock data used; BLS_API_KEY missing or MOCK_MODE=true.")
        return (
            {
            "energy_proxy_mom": 0.02,
            "gasoline_proxy_mom": 0.025,
            "food_proxy_mom": 0.003,
            "shelter_proxy_mom": 0.004,
            "core_goods_proxy_mom": -0.001,
            "core_services_ex_shelter_proxy_mom": 0.003,
            },
            warnings,
        )
    try:
        payload = _fetch_bls_series(settings.bls_api_key)
        if payload.get("status") != "REQUEST_SUCCEEDED":
            raise RuntimeError("BLS API request did not succeed")
        series_by_id = {item.get("seriesID"): item for item in payload.get("Results", {}).get("series", [])}
        result = {}
        asof_dates = []
        for output_key, series_id in BLS_CPI_SERIES.items():
            if series_id not in series_by_id:
                warnings.append(f"BLS CPI series missing: {series_id}.")
                continue
            try:
                mom, asof = _series_to_mom(series_by_id[series_id])
            except ValueError:
                warnings.append(f"BLS CPI series has insufficient observations: {series_id}.")
                continue
            result[output_key] = mom
            asof_dates.append(asof)
        if not result:
            raise RuntimeError("no usable BLS CPI series")
        if asof_dates:
            result["cpi_asof_date"] = max(asof_dates)
        return result, warnings
    except Exception as exc:
        warnings.append(f"BLS real-data fetch failed; CPI proxy missing. Reason: {type(exc).__name__}.")
        return {}, warnings
