import pandas as pd

from src.processors.rates import process_rates


def test_rates_use_latest_valid_observation_and_asof_dates():
    fred = pd.DataFrame(
            [
                {"date": "2026-06-05", "series_id": "DGS3MO", "value": "3.75"},
                {"date": "2026-06-05", "series_id": "DGS2", "value": "4.00"},
                {"date": "2026-06-05", "series_id": "DGS5", "value": "4.25"},
                {"date": "2026-06-05", "series_id": "DGS10", "value": "4.50"},
                {"date": "2026-06-05", "series_id": "DGS30", "value": "5.00"},
                {"date": "2026-06-05", "series_id": "T10Y2Y", "value": "0.50"},
                {"date": "2026-06-08", "series_id": "DGS10", "value": "."},
                {"date": "2026-06-08", "series_id": "T10Y2Y", "value": "0.55"},
        ]
    )

    result = process_rates(fred)
    latest = result.iloc[-1]

    assert latest["ten_year"] == 4.50
    assert latest["two_year"] == 4.00
    assert latest["ten_year_two_year_spread"] == 0.50
    assert latest["T10Y2Y"] == 0.55
    assert str(pd.to_datetime(latest["rates_curve_asof_date"]).date()) == "2026-06-05"
    assert str(pd.to_datetime(latest["ten_year_asof_date"]).date()) == "2026-06-05"
    assert str(pd.to_datetime(latest["two_year_asof_date"]).date()) == "2026-06-05"
    assert str(pd.to_datetime(latest["ten_year_two_year_spread_asof_date"]).date()) == "2026-06-05"
