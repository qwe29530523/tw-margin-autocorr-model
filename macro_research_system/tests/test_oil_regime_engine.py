from src.systems.oil_market.processors.oil_regime_engine import classify_oil_regime, empty_oil_summary


def test_tight_inventory_weak_products_regime():
    result = classify_oil_regime(
        {
            "oil_momentum_signal": "neutral",
            "inventory_signal": "inventory_tightening",
            "product_demand_signal": "broad_product_demand_softening",
            "crack_signal": "elevated_cracks",
            "supply_signal": "neutral",
        }
    )

    assert result["oil_regime"] == "tight_inventory_weak_products"


def test_inventory_building_weak_demand_regime():
    result = classify_oil_regime(
        {
            "oil_momentum_signal": "oil_down_medium_term",
            "inventory_signal": "inventory_building",
            "product_demand_signal": "broad_product_demand_softening",
            "crack_signal": "crack_weakening",
            "supply_signal": "neutral",
        }
    )

    assert result["oil_regime"] == "inventory_building_weak_demand"


def test_price_war_risk_rule():
    result = classify_oil_regime(
        {
            "oil_momentum_signal": "oil_down_medium_term",
            "inventory_signal": "inventory_building",
            "product_demand_signal": "broad_product_demand_softening",
            "crack_signal": "crack_weakening",
            "supply_signal": "us_supply_expanding_export_pressure",
        }
    )

    assert result["oil_regime"] == "price_war_risk"
    assert result["price_war_risk"] == "elevated"


def test_empty_oil_summary_schema_has_required_keys():
    summary = empty_oil_summary("2026-06-09")

    expected_keys = [
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
    assert list(summary.keys()) == expected_keys
    assert summary["system"] == "oil_market"
    assert summary["oil_regime"] == "mock_data_only"
