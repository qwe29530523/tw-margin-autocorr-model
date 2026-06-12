import pandas as pd

from src.systems.oil_market.charts.oil_crack_spread_chart import write_oil_crack_spread_chart
from src.systems.oil_market.charts.oil_dashboard_chart import write_oil_dashboard_chart
from src.systems.oil_market.charts.oil_inventory_chart import write_oil_inventory_chart
from src.systems.oil_market.charts.oil_price_chart import write_oil_price_chart
from src.systems.oil_market.charts.oil_product_demand_chart import write_oil_product_demand_chart


def _price_frame():
    return pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=70, freq="B"),
            "wti": [70 + index * 0.1 for index in range(70)],
            "brent": [73 + index * 0.1 for index in range(70)],
        }
    )


def _eia_frame():
    return pd.DataFrame(
        {
            "date": pd.date_range("2026-01-02", periods=30, freq="W-FRI"),
            "crude_inventory": [430000 + index * 31 + index * index for index in range(30)],
            "gasoline_inventory": [220000 + index * 19 + index * index for index in range(30)],
            "distillate_inventory": [120000 + index * 17 + index * index for index in range(30)],
            "gasoline_product_supplied": [8800 + index * 5 + index * index for index in range(30)],
            "distillate_product_supplied": [4000 + index * 4 + index * index for index in range(30)],
            "jet_fuel_product_supplied": [1500 + index * 3 + index * index for index in range(30)],
            "gasoline_crack_proxy": [18 + index * 0.17 for index in range(30)],
            "diesel_crack_proxy": [24 + index * 0.19 for index in range(30)],
        }
    )


def test_real_chart_titles_do_not_show_mock_banner(tmp_path, monkeypatch):
    titles = []

    def capture_title(self, label, *args, **kwargs):
        titles.append(label)
        return original_set_title(self, label, *args, **kwargs)

    import matplotlib.axes

    original_set_title = matplotlib.axes.Axes.set_title
    monkeypatch.setattr(matplotlib.axes.Axes, "set_title", capture_title)

    write_oil_price_chart(_price_frame(), tmp_path / "oil_price_momentum.png", mock_data_only=False)
    write_oil_inventory_chart(_eia_frame(), tmp_path / "oil_inventory_proxy.png", mock_data_only=False)
    write_oil_product_demand_chart(_eia_frame(), tmp_path / "oil_product_demand.png", mock_data_only=False)
    write_oil_crack_spread_chart(_eia_frame(), tmp_path / "oil_crack_spread.png", mock_data_only=False)

    assert "Oil Price Momentum" in titles
    assert "Oil Inventory Proxy 4W Change" in titles
    assert "Oil Product Demand 4W Change" in titles
    assert "Oil Crack Spread Proxy" in titles
    assert all("[MOCK DATA ONLY]" not in title for title in titles)


def test_mock_chart_titles_show_mock_banner(tmp_path, monkeypatch):
    titles = []

    def capture_title(self, label, *args, **kwargs):
        titles.append(label)
        return original_set_title(self, label, *args, **kwargs)

    import matplotlib.axes

    original_set_title = matplotlib.axes.Axes.set_title
    monkeypatch.setattr(matplotlib.axes.Axes, "set_title", capture_title)

    write_oil_price_chart(_price_frame(), tmp_path / "oil_price_momentum.png", mock_data_only=True)
    write_oil_inventory_chart(_eia_frame(), tmp_path / "oil_inventory_proxy.png", mock_data_only=True)
    write_oil_product_demand_chart(_eia_frame(), tmp_path / "oil_product_demand.png", mock_data_only=True)
    write_oil_crack_spread_chart(_eia_frame(), tmp_path / "oil_crack_spread.png", mock_data_only=True)

    assert "[MOCK DATA ONLY] Oil Price Momentum" in titles
    assert "[MOCK DATA ONLY] Oil Inventory Proxy 4W Change" in titles
    assert "[MOCK DATA ONLY] Oil Product Demand 4W Change" in titles
    assert "[MOCK DATA ONLY] Oil Crack Spread Proxy" in titles


def test_dashboard_title_aligns_real_and_mock_modes(tmp_path, monkeypatch):
    suptitles = []

    def capture_suptitle(self, text, *args, **kwargs):
        suptitles.append(text)
        return original_suptitle(self, text, *args, **kwargs)

    import matplotlib.figure

    original_suptitle = matplotlib.figure.Figure.suptitle
    monkeypatch.setattr(matplotlib.figure.Figure, "suptitle", capture_suptitle)

    write_oil_dashboard_chart(_price_frame(), _eia_frame(), tmp_path / "real_dashboard.png", mock_data_only=False)
    write_oil_dashboard_chart(_price_frame(), _eia_frame(), tmp_path / "mock_dashboard.png", mock_data_only=True)

    assert suptitles == ["Oil Market Dashboard", "[MOCK DATA ONLY] Oil Market Dashboard"]
