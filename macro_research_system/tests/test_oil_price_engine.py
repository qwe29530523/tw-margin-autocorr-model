import pandas as pd

from src.systems.oil_market.processors.oil_price_engine import build_oil_price_metrics


def test_oil_price_engine_computes_returns_and_short_term_signal():
    dates = pd.date_range("2026-01-01", periods=61, freq="B")
    frame = pd.DataFrame(
        {
            "date": dates,
            "wti": [90.0] * 56 + [96.0, 97.0, 98.0, 99.0, 100.0],
            "brent": [92.0] * 56 + [98.0, 99.0, 100.0, 101.0, 102.0],
        }
    )

    result = build_oil_price_metrics(frame)

    assert result["wti"] == 100.0
    assert result["brent_wti_spread"] == 2.0
    assert result["wti_return_5d"] > 0.05
    assert result["oil_momentum_signal"] == "oil_up_short_term"
