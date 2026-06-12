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


def _to_float(value) -> float | None:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _series_to_mom(series: dict) -> tuple[float, str]:
    rows = []
    for item in series.get("data", []):
        if not str(item.get("period", "")).startswith("M") or item.get("period") == "M13":
            continue
        value = _to_float(item.get("value"))
        if value is None:
            continue
        rows.append({**item, "numeric_value": value})
    rows = sorted(rows, key=lambda item: (int(item["year"]), int(item["period"][1:])))
    if len(rows) < 2:
        raise ValueError("not enough monthly CPI observations")
    latest = rows[-1]
    previous = rows[-2]
    mom = latest["numeric_value"] / previous["numeric_value"] - 1
    asof = f"{latest['year']}-{latest['period'][1:]}"
    return mom, asof


def _series_to_mom_trend(series: dict, periods: int = 24) -> list[dict]:
    rows = []
    for item in series.get("data", []):
        if not str(item.get("period", "")).startswith("M") or item.get("period") == "M13":
            continue
        value = _to_float(item.get("value"))
        if value is None:
            continue
        rows.append({**item, "numeric_value": value})
    rows = sorted(rows, key=lambda item: (int(item["year"]), int(item["period"][1:])))
    trend = []
    previous_value = None
    for item in rows[-(periods + 1) :]:
        value = item["numeric_value"]
        month = f"{item['year']}-{item['period'][1:]}"
        if previous_value is not None:
            trend.append({"month": month, "value": value, "mom": value / previous_value - 1})
        previous_value = value
    return trend[-periods:]


def _mock_bls_cpi_components() -> dict:
    return {
        "energy_proxy_mom": 0.02,
        "gasoline_proxy_mom": 0.025,
        "food_proxy_mom": 0.003,
        "shelter_proxy_mom": 0.004,
        "core_goods_proxy_mom": -0.001,
        "core_services_ex_shelter_proxy_mom": 0.003,
        "cpi_asof_month": "2026-05",
        "component_trends": {
            "energy_proxy_mom": [
                {"month": "2026-03", "value": 100.0, "mom": -0.005},
                {"month": "2026-04", "value": 101.0, "mom": 0.010},
                {"month": "2026-05", "value": 103.02, "mom": 0.020},
            ],
            "food_proxy_mom": [
                {"month": "2026-03", "value": 100.0, "mom": 0.002},
                {"month": "2026-04", "value": 100.2, "mom": 0.002},
                {"month": "2026-05", "value": 100.5, "mom": 0.003},
            ],
            "shelter_proxy_mom": [
                {"month": "2026-03", "value": 100.0, "mom": 0.003},
                {"month": "2026-04", "value": 100.3, "mom": 0.003},
                {"month": "2026-05", "value": 100.7, "mom": 0.004},
            ],
            "core_goods_proxy_mom": [
                {"month": "2026-03", "value": 100.0, "mom": 0.001},
                {"month": "2026-04", "value": 100.0, "mom": 0.000},
                {"month": "2026-05", "value": 99.9, "mom": -0.001},
            ],
            "core_services_ex_shelter_proxy_mom": [
                {"month": "2026-03", "value": 100.0, "mom": 0.002},
                {"month": "2026-04", "value": 100.2, "mom": 0.002},
                {"month": "2026-05", "value": 100.5, "mom": 0.003},
            ],
        },
    }


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


def fetch_bls_cpi_components(settings: Settings) -> tuple[dict, list[str], str]:
    if settings.mock_mode or not settings.bls_api_key:
        return _mock_bls_cpi_components(), ["MOCK DATA ONLY: BLS CPI fixture data used."], "mock"
    warnings: list[str] = []
    try:
        payload = _fetch_bls_series(settings.bls_api_key)
        if payload.get("status") != "REQUEST_SUCCEEDED":
            raise RuntimeError("BLS API request did not succeed")
        series_by_id = {item.get("seriesID"): item for item in payload.get("Results", {}).get("series", [])}
        result = {}
        component_trends = {}
        asof_months = []
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
            component_trends[output_key] = _series_to_mom_trend(series_by_id[series_id])
            asof_months.append(asof)
        if not result:
            raise RuntimeError("no usable BLS CPI series")
        if asof_months:
            result["cpi_asof_month"] = max(asof_months)
        result["component_trends"] = component_trends
        return result, warnings, "real"
    except Exception as exc:
        warnings.append(f"BLS CPI fetch failed; using mock data. Reason: {type(exc).__name__}.")
        return _mock_bls_cpi_components(), warnings, "fallback_mock"
