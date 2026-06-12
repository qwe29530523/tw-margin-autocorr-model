from src.systems.oil_rates_cpi.fetchers.fred_fetcher import _observations_to_frame
from src.systems.oil_rates_cpi.fetchers.bls_fetcher import _series_to_mom


def test_fred_observations_to_frame_skips_dot_values():
    payload = {
        "observations": [
            {"date": "2026-06-01", "value": "."},
            {"date": "2026-06-02", "value": "4.25"},
        ]
    }

    frame = _observations_to_frame(payload, "DGS10")

    assert len(frame) == 1
    assert frame.iloc[0]["series"] == "DGS10"
    assert frame.iloc[0]["value"] == 4.25


def test_bls_series_to_mom_uses_latest_monthly_values():
    series = {
        "data": [
            {"year": "2026", "period": "M02", "value": "101.0"},
            {"year": "2026", "period": "M01", "value": "100.0"},
            {"year": "2025", "period": "M13", "value": "99.0"},
        ]
    }

    mom, asof = _series_to_mom(series)

    assert round(mom, 4) == 0.01
    assert asof == "2026-02"
