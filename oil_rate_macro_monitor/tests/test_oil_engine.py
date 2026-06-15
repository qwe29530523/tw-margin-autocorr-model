import pandas as pd

from src.processors.oil_engine import build_oil_frame


def test_oil_engine_uses_fred_prices_and_eia_product_demand_without_yahoo():
    dates = pd.date_range("2026-01-01", periods=5, freq="7D")
    fred_rows = []
    eia_rows = []
    for idx, date in enumerate(dates):
        fred_rows.extend(
            [
                {"date": date, "series_id": "DCOILWTICO", "value": 80.0 + idx * 2},
                {"date": date, "series_id": "DCOILBRENTEU", "value": 83.0 + idx * 2.25},
            ]
        )
        eia_rows.extend(
            [
                {"date": date, "series_id": "WCESTUS1", "value": 400000 - idx * 2500, "units": "MBBL"},
                {"date": date, "series_id": "WGTSTUS1", "value": 220000 - idx * 2500, "units": "MBBL"},
                {"date": date, "series_id": "WDISTUS1", "value": 120000 - idx * 500, "units": "MBBL"},
                {"date": date, "series_id": "WGFUPUS2", "value": 8000 + idx * 100, "units": "MBBL/D"},
                {"date": date, "series_id": "WDIUPUS2", "value": 3500 - idx * 50, "units": "MBBL/D"},
            ]
        )
    fred = pd.DataFrame(fred_rows)
    eia = pd.DataFrame(eia_rows)

    result = build_oil_frame(fred, eia)
    latest = result.iloc[-1]

    assert latest["wti"] == 88.0
    assert latest["brent_wti_spread"] == 4.0
    assert latest["total_inventory_proxy_4w_change"] < 0
    assert latest["inventory_signal"] == "inventory_tightening"
    assert latest["gasoline_product_supplied_4w_change"] > 0
    assert "product_demand_signal" in result.columns


def test_oil_engine_flags_broad_product_softening_when_all_product_supplied_changes_are_negative():
    dates = pd.date_range("2026-01-01", periods=5, freq="7D")
    fred_rows = []
    eia_rows = []
    for idx, date in enumerate(dates):
        fred_rows.extend(
            [
                {"date": date, "series_id": "DCOILWTICO", "value": 80.0},
                {"date": date, "series_id": "DCOILBRENTEU", "value": 84.0},
            ]
        )
        eia_rows.extend(
            [
                {"date": date, "series_id": "WCESTUS1", "value": 400000 - idx * 1000, "units": "MBBL"},
                {"date": date, "series_id": "WGTSTUS1", "value": 220000, "units": "MBBL"},
                {"date": date, "series_id": "WDISTUS1", "value": 120000, "units": "MBBL"},
                {"date": date, "series_id": "WGFUPUS2", "value": 9000 - idx * 100, "units": "MBBL/D"},
                {"date": date, "series_id": "WDIUPUS2", "value": 4200 - idx * 80, "units": "MBBL/D"},
                {"date": date, "series_id": "WKJUPUS2", "value": 1700 - idx * 40, "units": "MBBL/D"},
                {"date": date, "series_id": "EMM_EPMR_PTE_NUS_DPG", "value": 3.9, "units": "Dollars per Gallon"},
                {"date": date, "series_id": "EMD_EPD2D_PTE_NUS_DPG", "value": 4.5, "units": "Dollars per Gallon"},
            ]
        )

    result = build_oil_frame(pd.DataFrame(fred_rows), pd.DataFrame(eia_rows))
    latest = result.iloc[-1]

    assert latest["gasoline_product_supplied_4w_change"] < 0
    assert latest["distillate_product_supplied_4w_change"] < 0
    assert latest["jet_fuel_product_supplied_4w_change"] < 0
    assert latest["product_demand_signal"] == "product_demand_softening_with_elevated_cracks"
