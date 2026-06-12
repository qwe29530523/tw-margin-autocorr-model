from __future__ import annotations

from src.systems.oil_rates_cpi.processors.cpi_weights import default_cpi_weights


def build_cpi_nowcast(components: dict) -> dict:
    weights = default_cpi_weights()
    used_fields = [key for key in components if not key.startswith("actual_")]
    energy = components.get("energy_proxy_mom", 0.0) * weights["energy"]
    gasoline = components.get("gasoline_proxy_mom", components.get("energy_proxy_mom", 0.0)) * weights["gasoline"]
    food = components.get("food_proxy_mom", 0.0) * weights["food"]
    shelter = components.get("shelter_proxy_mom", 0.0) * weights["shelter"]
    core_goods = components.get("core_goods_proxy_mom", 0.0) * weights["core_goods"]
    core_services = components.get("core_services_ex_shelter_proxy_mom", 0.0) * weights["core_services_ex_shelter"]
    headline_mom = energy + food + shelter + core_goods + core_services
    core_mom = shelter + core_goods + core_services
    missing_core = [name for name in ["shelter_proxy_mom", "core_goods_proxy_mom", "core_services_ex_shelter_proxy_mom"] if name not in components]
    confidence = 80 - len(missing_core) * 15
    warnings = []
    if missing_core:
        warnings.append("Core CPI proxy incomplete; confidence lowered.")
    return {
        "cpi_nowcast_signal": "inflationary" if headline_mom > 0.004 else "disinflationary",
        "headline_cpi_mom_nowcast": round(headline_mom, 4),
        "headline_cpi_yoy_nowcast": round(headline_mom * 12, 4),
        "core_cpi_mom_nowcast": round(core_mom, 4),
        "core_cpi_yoy_nowcast": round(core_mom * 12, 4),
        "energy_contribution": round(energy, 4),
        "gasoline_contribution": round(gasoline, 4),
        "food_contribution": round(food, 4),
        "shelter_contribution": round(shelter, 4),
        "core_goods_contribution": round(core_goods, 4),
        "core_services_ex_shelter_contribution": round(core_services, 4),
        "confidence_score": confidence,
        "expected_range": [round(headline_mom - 0.001, 4), round(headline_mom + 0.001, 4)],
        "warnings": warnings,
        "used_fields": used_fields,
        "cpi_asof_date": components.get("cpi_asof_date"),
    }
