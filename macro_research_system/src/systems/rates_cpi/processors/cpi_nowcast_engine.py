from __future__ import annotations


CPI_WEIGHTS = {
    "energy": 0.074,
    "gasoline": 0.035,
    "food": 0.134,
    "shelter": 0.356,
    "core_goods": 0.189,
    "core_services_ex_shelter": 0.247,
}


def build_cpi_nowcast(components: dict) -> dict:
    if not components:
        return {
            "cpi_asof_month": None,
            "cpi_nowcast_signal": "unknown",
            "headline_cpi_mom_nowcast": None,
            "headline_cpi_yoy_nowcast": None,
            "core_cpi_mom_nowcast": None,
            "core_cpi_yoy_nowcast": None,
            "warnings": ["CPI nowcast components missing."],
        }
    energy = components.get("energy_proxy_mom", 0.0) * CPI_WEIGHTS["energy"]
    gasoline = components.get("gasoline_proxy_mom", components.get("energy_proxy_mom", 0.0)) * CPI_WEIGHTS["gasoline"]
    food = components.get("food_proxy_mom", 0.0) * CPI_WEIGHTS["food"]
    shelter = components.get("shelter_proxy_mom", 0.0) * CPI_WEIGHTS["shelter"]
    core_goods = components.get("core_goods_proxy_mom", 0.0) * CPI_WEIGHTS["core_goods"]
    core_services = components.get("core_services_ex_shelter_proxy_mom", 0.0) * CPI_WEIGHTS["core_services_ex_shelter"]
    headline = energy + food + shelter + core_goods + core_services
    core = shelter + core_goods + core_services
    missing_core = [
        name
        for name in ["shelter_proxy_mom", "core_goods_proxy_mom", "core_services_ex_shelter_proxy_mom"]
        if name not in components
    ]
    warnings = ["Core CPI proxy incomplete; confidence lowered."] if missing_core else []
    return {
        "cpi_asof_month": components.get("cpi_asof_month"),
        "cpi_nowcast_signal": "inflationary" if headline > 0.004 else "disinflationary",
        "headline_cpi_mom_nowcast": round(headline, 6),
        "headline_cpi_yoy_nowcast": round(headline * 12, 6),
        "core_cpi_mom_nowcast": round(core, 6),
        "core_cpi_yoy_nowcast": round(core * 12, 6),
        "warnings": warnings,
    }
