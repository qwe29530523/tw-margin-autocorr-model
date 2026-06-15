from src.processors.signals import generate_macro_regime


def test_oil_up_rates_up_inventory_tightening_outputs_inflation_pressure():
    result = generate_macro_regime(
        oil_20d_return=0.07,
        oil_5d_return=0.02,
        crack_signal="industrial_logistics_strength",
        inventory_signal="inventory_tightening",
        rate_signal="rates_up",
        usd_trend="mixed",
    )

    assert result["regime"] == "inflation_pressure"


def test_oil_down_rates_down_inventory_building_outputs_recession_pressure():
    result = generate_macro_regime(
        oil_20d_return=-0.08,
        oil_5d_return=-0.03,
        crack_signal="demand_weakening",
        inventory_signal="inventory_building",
        rate_signal="rates_down",
        usd_trend="mixed",
    )

    assert result["regime"] == "recession_pressure"


def test_oil_up_rates_down_outputs_stagflation_or_supply_shock():
    result = generate_macro_regime(
        oil_20d_return=0.06,
        oil_5d_return=0.06,
        crack_signal="mixed",
        inventory_signal="inventory_tightening",
        rate_signal="rates_down",
        usd_trend="mixed",
    )

    assert result["regime"] in {"stagflation_risk", "supply_shock"}


def test_tight_inventory_and_weak_products_sets_secondary_regime():
    result = generate_macro_regime(
        oil_20d_return=0.0,
        oil_5d_return=0.0,
        crack_signal="demand_weakening",
        inventory_signal="inventory_tightening",
        rate_signal="mixed",
        usd_trend="mixed",
    )

    assert result["secondary_regime"] == "tight_inventory_weak_products"
