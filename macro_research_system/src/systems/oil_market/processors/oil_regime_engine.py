from __future__ import annotations


SUMMARY_KEYS = [
    "system",
    "report_date",
    "data_source_mode",
    "fred_real_data",
    "eia_real_data",
    "mock_mode",
    "real_data_ready",
    "data_validation_passed",
    "data_validation_warnings",
    "data_completeness_score",
    "regime_confidence_score",
    "oil_regime",
    "oil_momentum_signal",
    "inventory_signal",
    "product_demand_signal",
    "crack_signal",
    "refinery_signal",
    "supply_signal",
    "price_war_risk",
    "supply_shock_risk",
    "demand_destruction_risk",
    "oil_asof_date",
    "inventory_asof_date",
    "product_demand_asof_date",
    "wti",
    "brent",
    "brent_wti_spread",
    "wti_return_5d",
    "wti_return_20d",
    "wti_return_60d",
    "brent_return_5d",
    "brent_return_20d",
    "brent_return_60d",
    "crude_inventory_4w_change",
    "gasoline_inventory_4w_change",
    "distillate_inventory_4w_change",
    "total_inventory_proxy_4w_change",
    "gasoline_product_supplied_4w_change",
    "distillate_product_supplied_4w_change",
    "jet_fuel_product_supplied_4w_change",
    "refinery_utilization",
    "refinery_crude_inputs",
    "crude_production",
    "crude_exports",
    "gasoline_crack_proxy",
    "diesel_crack_proxy",
    "gasoline_crack_20d_change",
    "diesel_crack_20d_change",
    "warnings",
]


def empty_oil_summary(report_date: str) -> dict:
    summary = {key: None for key in SUMMARY_KEYS}
    summary.update(
        {
            "system": "oil_market",
            "report_date": report_date,
            "data_source_mode": "Core FRED + EIA",
            "fred_real_data": False,
            "eia_real_data": False,
            "mock_mode": True,
            "real_data_ready": False,
            "data_validation_passed": False,
            "data_validation_warnings": [],
            "data_completeness_score": 0,
            "regime_confidence_score": 0,
            "oil_regime": "mock_data_only",
            "oil_momentum_signal": "neutral",
            "inventory_signal": "neutral",
            "product_demand_signal": "neutral",
            "crack_signal": "neutral",
            "refinery_signal": "neutral",
            "supply_signal": "neutral",
            "price_war_risk": "low",
            "supply_shock_risk": "low",
            "demand_destruction_risk": "low",
            "warnings": [],
        }
    )
    return summary


def classify_oil_regime(metrics: dict) -> dict:
    momentum = metrics.get("oil_momentum_signal", "neutral")
    inventory = metrics.get("inventory_signal", "neutral")
    demand = metrics.get("product_demand_signal", "neutral")
    crack = metrics.get("crack_signal", "neutral")
    supply = metrics.get("supply_signal", "neutral")

    if (
        momentum in {"oil_down_short_term", "oil_down_medium_term"}
        and inventory == "inventory_building"
        and crack == "crack_weakening"
        and supply == "us_supply_expanding_export_pressure"
    ):
        regime = "price_war_risk"
    elif momentum == "oil_up_short_term" and inventory == "inventory_tightening" and supply in {
        "us_supply_tight",
        "export_pressure_high",
    }:
        regime = "supply_shock"
    elif inventory == "inventory_building" and demand == "broad_product_demand_softening" and momentum == "oil_down_medium_term":
        regime = "inventory_building_weak_demand"
    elif inventory == "inventory_tightening" and demand == "broad_product_demand_softening" and crack in {
        "elevated_cracks",
        "product_demand_softening_with_elevated_cracks",
        "mixed_product_demand",
        "neutral",
    }:
        regime = "tight_inventory_weak_products"
    elif inventory == "inventory_tightening" and momentum in {"oil_up_short_term", "oil_up_medium_term"}:
        regime = "supply_led_tightness"
    elif (
        momentum == "oil_up_medium_term"
        and demand == "broad_product_demand_strength"
        and crack == "crack_strengthening"
        and inventory != "inventory_building"
    ):
        regime = "demand_led_strength"
    else:
        regime = "neutral_mixed"

    return {
        "oil_regime": regime,
        "price_war_risk": "elevated" if regime == "price_war_risk" else "low",
        "supply_shock_risk": "elevated" if regime == "supply_shock" else "low",
        "demand_destruction_risk": "elevated"
        if regime in {"inventory_building_weak_demand", "price_war_risk"}
        else "low",
    }


def score_data_completeness(summary: dict) -> int:
    required = [
        "wti",
        "brent",
        "crude_inventory_4w_change",
        "gasoline_inventory_4w_change",
        "distillate_inventory_4w_change",
        "gasoline_product_supplied_4w_change",
        "distillate_product_supplied_4w_change",
        "jet_fuel_product_supplied_4w_change",
        "gasoline_crack_proxy",
        "diesel_crack_proxy",
    ]
    available = sum(summary.get(key) is not None for key in required)
    return int(round(available / len(required) * 100))


def score_regime_confidence(summary: dict) -> int:
    score = 35 + round(score_data_completeness(summary) * 0.45)
    if any("mock" in str(item).lower() for item in summary.get("warnings", [])):
        score -= 10
    return int(max(0, min(100, score)))
