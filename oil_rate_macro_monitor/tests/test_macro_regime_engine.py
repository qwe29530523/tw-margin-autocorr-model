import pandas as pd

from src.processors.macro_regime_engine import build_macro_summary


def test_macro_summary_sets_tight_inventory_weak_products_secondary_regime():
    oil = pd.DataFrame(
        [
            {
                "date": "2026-06-05",
                "oil_momentum_signal": "oil_flat",
                "inventory_signal": "inventory_tightening",
                "product_demand_signal": "demand_weakening",
                "oil_regime": "tight_inventory_weak_products",
                "price_war_risk": "low",
            }
        ]
    )
    rates = pd.DataFrame(
        [
            {
                "date": "2026-06-05",
                "rates_regime": "mixed",
                "carry_signal": "negative_carry",
                "funding_pressure_signal": "mixed",
            }
        ]
    )

    summary = build_macro_summary(oil, rates, yahoo_overlay=False)

    assert summary["macro_regime"] == "neutral_mixed"
    assert summary["secondary_regime"] == "tight_inventory_weak_products"
    assert "Yahoo overlay OFF" in summary["warnings"]


def test_macro_summary_splits_data_completeness_and_regime_confidence_scores():
    oil = pd.DataFrame(
        [
            {
                "date": "2026-06-05",
                "wti": 90.0,
                "brent": 94.0,
                "crude_inventory": 410000,
                "gasoline_inventory": 220000,
                "distillate_inventory": 120000,
                "gasoline_product_supplied": 9000,
                "distillate_product_supplied": 4200,
                "jet_fuel_product_supplied": 1700,
                "oil_momentum_signal": "oil_flat",
                "inventory_signal": "inventory_tightening",
                "product_demand_signal": "product_demand_softening_with_elevated_cracks",
                "oil_regime": "tight_inventory_weak_products",
                "curve_state": "unknown",
            }
        ]
    )
    rates = pd.DataFrame(
        [
            {
                "date": "2026-06-05",
                "fedfunds": 4.0,
                "sofr": 4.01,
                "three_month": 4.1,
                "two_year": 4.2,
                "five_year": 4.3,
                "ten_year": 4.4,
                "thirty_year": 4.8,
                "rates_regime": "belly_normal",
                "carry_signal": "carry_repair",
                "funding_pressure_signal": "funding_pressure_low",
            }
        ]
    )

    summary = build_macro_summary(oil, rates, yahoo_overlay=False)

    assert "data_completeness_score" in summary
    assert "regime_confidence_score" in summary
    assert summary["data_completeness_score"] >= summary["regime_confidence_score"]
    assert summary["regime_confidence_score"] < 75
