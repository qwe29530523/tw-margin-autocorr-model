import pandas as pd

from src.common.settings import Settings
from src.systems.oil_market.fetchers import eia_fetcher, fred_fetcher


def test_fred_fetcher_real_mode_requests_wti_and_brent(monkeypatch):
    calls = []

    def fake_fetch(api_key, series_id):
        calls.append((api_key, series_id))
        return pd.DataFrame(
            {
                "date": pd.date_range("2026-01-01", periods=3, freq="B"),
                "value": [70.0, 71.0, 72.0],
            }
        )

    monkeypatch.setattr(fred_fetcher, "_fetch_fred_observations", fake_fetch)
    settings = Settings("fred-key", "eia-key", None, False, False)

    frame, warnings, source_mode = fred_fetcher.fetch_oil_price_frame(settings)

    assert source_mode == "real"
    assert warnings == []
    assert {series_id for _, series_id in calls} == {"DCOILWTICO", "DCOILBRENTEU"}
    assert {"wti", "brent"}.issubset(frame.columns)


def test_fred_fetcher_fallback_warning_includes_reason(monkeypatch):
    def fail_fetch(api_key, series_id):
        raise RuntimeError("simulated FRED outage")

    monkeypatch.setattr(fred_fetcher, "_fetch_fred_observations", fail_fetch)
    settings = Settings("fred-key", "eia-key", None, False, False)

    frame, warnings, source_mode = fred_fetcher.fetch_oil_price_frame(settings)

    assert source_mode == "fallback_mock"
    assert not frame.empty
    assert any("Reason: RuntimeError" in item for item in warnings)


def test_eia_fetcher_real_mode_requests_required_weekly_series(monkeypatch):
    legacy_calls = []

    def fake_legacy(api_key, series_id):
        legacy_calls.append((api_key, series_id))
        return pd.DataFrame(
            {
                "date": pd.date_range("2026-01-02", periods=3, freq="W-FRI"),
                "value": [100.0, 101.0, 102.0],
            }
        )

    def fake_spot(api_key):
        return pd.DataFrame(
            {
                "date": pd.date_range("2026-01-01", periods=20, freq="B"),
                "wti_spot_price": [70.0 + index for index in range(20)],
                "gasoline_spot_price": [2.0 + index * 0.01 for index in range(20)],
                "diesel_spot_price": [2.4 + index * 0.01 for index in range(20)],
            }
        )

    monkeypatch.setattr(eia_fetcher, "_fetch_legacy_series", fake_legacy)
    monkeypatch.setattr(eia_fetcher, "_fetch_spot_price_frame", fake_spot)
    settings = Settings("fred-key", "eia-key", None, False, False)

    frame, warnings, source_mode = eia_fetcher.fetch_eia_oil_frame(settings)

    assert source_mode == "real"
    assert warnings == []
    assert {series_id for _, series_id in legacy_calls} == set(eia_fetcher.EIA_LEGACY_SERIES)
    assert {"crude_inventory", "gasoline_product_supplied", "crude_exports"}.issubset(frame.columns)


def test_eia_fetcher_fallback_warning_includes_reason(monkeypatch):
    def fail_legacy(api_key, series_id):
        raise RuntimeError("simulated EIA outage")

    monkeypatch.setattr(eia_fetcher, "_fetch_legacy_series", fail_legacy)
    settings = Settings("fred-key", "eia-key", None, False, False)

    frame, warnings, source_mode = eia_fetcher.fetch_eia_oil_frame(settings)

    assert source_mode == "fallback_mock"
    assert not frame.empty
    assert any("Reason: RuntimeError" in item for item in warnings)
