import pandas as pd

from src.systems.oil_rates_cpi.processors.oil_engine import build_oil_metrics


def test_oil_inventory_signal():
    frame = pd.DataFrame(
        [
            {"date": "2026-01-01", "crude_inventory": 410000, "gasoline_inventory": 220000, "distillate_inventory": 120000},
            {"date": "2026-01-29", "crude_inventory": 398000, "gasoline_inventory": 218000, "distillate_inventory": 119000},
        ]
    )

    result = build_oil_metrics(frame)

    assert result["inventory_signal"] == "inventory_tightening"


def test_product_demand_softening_with_elevated_cracks():
    frame = pd.DataFrame(
        [
            {
                "date": "2026-01-01",
                "gasoline_product_supplied": 9000,
                "distillate_product_supplied": 4200,
                "jet_fuel_product_supplied": 1700,
                "gasoline_crack_proxy": 80,
                "diesel_crack_proxy": 120,
            },
            {
                "date": "2026-01-29",
                "gasoline_product_supplied": 8800,
                "distillate_product_supplied": 4100,
                "jet_fuel_product_supplied": 1600,
                "gasoline_crack_proxy": 82,
                "diesel_crack_proxy": 125,
            },
        ]
    )

    result = build_oil_metrics(frame)

    assert result["product_demand_signal"] == "product_demand_softening_with_elevated_cracks"
