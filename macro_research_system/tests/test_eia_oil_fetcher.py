import pandas as pd

from src.systems.oil_market.fetchers.eia_fetcher import _attach_crack_spread_proxy


def test_attach_crack_spread_proxy_uses_latest_prior_spot_and_gallon_conversion():
    weekly = pd.DataFrame({"date": pd.to_datetime(["2026-05-22", "2026-05-29"])})
    spot = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-05-21", "2026-05-28"]),
            "wti_spot_price": [70.0, 80.0],
            "gasoline_spot_price": [2.0, 2.5],
            "diesel_spot_price": [2.4, 2.8],
        }
    )

    result = _attach_crack_spread_proxy(weekly, spot)

    latest = result.iloc[-1]
    assert latest["crack_spread_asof_date"] == "2026-05-28"
    assert latest["gasoline_crack_proxy"] == 25.0
    assert latest["diesel_crack_proxy"] == 37.6
