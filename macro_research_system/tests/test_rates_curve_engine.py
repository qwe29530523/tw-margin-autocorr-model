import pandas as pd

from src.common.settings import Settings
from src.systems.oil_rates_cpi.fetchers.fred_fetcher import fetch_fred_series
from src.systems.oil_rates_cpi.processors.rates_curve_engine import build_rates_curve_metrics


def test_rates_curve_same_date_calculation():
    frame = pd.DataFrame(
        [
            {"date": "2026-06-04", "series": "DGS3MO", "value": 3.78},
            {"date": "2026-06-04", "series": "DGS2", "value": 4.05},
            {"date": "2026-06-04", "series": "DGS5", "value": 4.18},
            {"date": "2026-06-04", "series": "DGS10", "value": 4.47},
            {"date": "2026-06-04", "series": "DGS30", "value": 4.97},
            {"date": "2026-06-05", "series": "T10Y2Y", "value": 0.38},
        ]
    )

    result = build_rates_curve_metrics(frame)

    assert result["rates_curve_asof_date"] == "2026-06-04"
    assert result["ten_year_two_year_spread"] == 0.42
    assert result["ten_year_two_year_spread_fred"] == 0.38


def test_funding_pressure_thresholds():
    frame = pd.DataFrame(
        [
            {"date": "2026-06-04", "series": "FEDFUNDS", "value": 4.00},
            {"date": "2026-06-04", "series": "SOFR", "value": 4.31},
            {"date": "2026-06-04", "series": "DGS3MO", "value": 4.10},
            {"date": "2026-06-04", "series": "DGS2", "value": 4.20},
            {"date": "2026-06-04", "series": "DGS5", "value": 4.30},
            {"date": "2026-06-04", "series": "DGS10", "value": 4.50},
            {"date": "2026-06-04", "series": "DGS30", "value": 5.00},
        ]
    )

    result = build_rates_curve_metrics(frame)

    assert result["funding_pressure_signal"] == "funding_pressure_stress"


def test_carry_repair_signal():
    frame = pd.DataFrame(
        [
            {"date": "2026-05-01", "series": "SOFR", "value": 4.00},
            {"date": "2026-05-01", "series": "DGS3MO", "value": 3.70},
            {"date": "2026-05-01", "series": "DGS2", "value": 3.80},
            {"date": "2026-05-01", "series": "DGS5", "value": 3.90},
            {"date": "2026-05-01", "series": "DGS10", "value": 4.00},
            {"date": "2026-05-01", "series": "DGS30", "value": 4.50},
            {"date": "2026-06-04", "series": "FEDFUNDS", "value": 3.90},
            {"date": "2026-06-04", "series": "SOFR", "value": 4.00},
            {"date": "2026-06-04", "series": "DGS3MO", "value": 3.80},
            {"date": "2026-06-04", "series": "DGS2", "value": 4.20},
            {"date": "2026-06-04", "series": "DGS5", "value": 4.35},
            {"date": "2026-06-04", "series": "DGS10", "value": 4.70},
            {"date": "2026-06-04", "series": "DGS30", "value": 5.10},
        ]
    )

    result = build_rates_curve_metrics(frame)

    assert result["carry_signal"] == "carry_repair"


def test_mock_fred_fixture_has_nonzero_one_year():
    settings = Settings(
        fred_api_key=None,
        eia_api_key=None,
        bls_api_key=None,
        use_yahoo=False,
        mock_mode=True,
    )

    frame, warnings = fetch_fred_series(settings)

    dgs1 = frame[frame["series"] == "DGS1"]
    assert not dgs1.empty
    assert (dgs1["value"] > 0).all()
    assert any("mock data" in item for item in warnings)


def test_rates_missing_one_year_outputs_missing_not_zero():
    frame = pd.DataFrame(
        [
            {"date": "2026-06-04", "series": "FEDFUNDS", "value": 4.00},
            {"date": "2026-06-04", "series": "SOFR", "value": 4.01},
            {"date": "2026-06-04", "series": "DGS3MO", "value": 3.78},
            {"date": "2026-06-04", "series": "DGS2", "value": 4.05},
            {"date": "2026-06-04", "series": "DGS5", "value": 4.18},
            {"date": "2026-06-04", "series": "DGS10", "value": 4.47},
            {"date": "2026-06-04", "series": "DGS30", "value": 4.97},
        ]
    )

    result = build_rates_curve_metrics(frame)

    assert result["one_year"] == "missing"


def test_rates_change_uses_recent_20_complete_curve_observations():
    rows = []
    for index, date in enumerate(pd.date_range("2026-01-01", periods=25, freq="B")):
        for series, value in [
            ("DGS3MO", 3.0),
            ("DGS2", 4.0 + index * 0.01),
            ("DGS5", 4.1 + index * 0.02),
            ("DGS10", 4.2 + index * 0.01),
            ("DGS30", 4.7),
            ("SOFR", 4.0),
            ("FEDFUNDS", 4.0),
        ]:
            rows.append({"date": date, "series": series, "value": value})

    result = build_rates_curve_metrics(pd.DataFrame(rows))

    assert round(result["two_year_change_20d"], 4) == 0.20
    assert round(result["five_year_change_20d"], 4) == 0.40
