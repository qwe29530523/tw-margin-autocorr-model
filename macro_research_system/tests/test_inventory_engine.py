import pandas as pd

from src.systems.oil_market.processors.inventory_engine import build_inventory_metrics


def test_inventory_tightening_rule():
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=5, freq="W"),
            "crude_inventory": [100, 99, 98, 96, 94],
            "gasoline_inventory": [50, 49, 48, 47, 46],
            "distillate_inventory": [30, 29, 28, 27, 26],
        }
    )

    result = build_inventory_metrics(frame)

    assert result["total_inventory_proxy_4w_change"] < 0
    assert result["inventory_signal"] == "inventory_tightening"


def test_inventory_mixed_cross_signal_rule():
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=5, freq="W"),
            "crude_inventory": [100, 99, 98, 97, 96],
            "gasoline_inventory": [50, 51, 52, 53, 54],
            "distillate_inventory": [30, 30, 30, 30, 30],
        }
    )

    result = build_inventory_metrics(frame)

    assert result["inventory_signal"] == "crude_tight_product_loose"
