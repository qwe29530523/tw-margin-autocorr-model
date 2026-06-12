import pandas as pd

from src.systems.oil_market.processors.crack_spread_engine import build_crack_spread_metrics


def test_product_demand_softening_with_elevated_cracks_rule():
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=25, freq="B"),
            "gasoline_crack_proxy": list(range(25)),
            "diesel_crack_proxy": list(range(5, 30)),
        }
    )

    result = build_crack_spread_metrics(frame, product_demand_signal="broad_product_demand_softening")

    assert result["gasoline_crack_20d_change"] > 0
    assert result["diesel_crack_20d_change"] > 0
    assert result["crack_signal"] == "product_demand_softening_with_elevated_cracks"
