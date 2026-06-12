import pandas as pd

from src.systems.oil_market.processors.product_demand_engine import build_product_demand_metrics


def test_product_demand_softening_rule():
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=5, freq="W"),
            "gasoline_product_supplied": [100, 99, 98, 97, 96],
            "distillate_product_supplied": [80, 79, 78, 77, 76],
            "jet_fuel_product_supplied": [60, 59, 58, 57, 56],
        }
    )

    result = build_product_demand_metrics(frame)

    assert result["gasoline_product_supplied_4w_change"] < 0
    assert result["product_demand_signal"] == "broad_product_demand_softening"


def test_product_demand_strength_rule():
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=5, freq="W"),
            "gasoline_product_supplied": [100, 101, 102, 103, 104],
            "distillate_product_supplied": [80, 81, 82, 83, 84],
            "jet_fuel_product_supplied": [60, 61, 62, 63, 64],
        }
    )

    result = build_product_demand_metrics(frame)

    assert result["product_demand_signal"] == "broad_product_demand_strength"
