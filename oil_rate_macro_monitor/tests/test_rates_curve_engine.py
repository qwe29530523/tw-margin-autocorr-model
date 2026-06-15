import pytest
import pandas as pd

from src.processors.rates_curve_engine import build_rates_curve_frame


def test_rates_curve_engine_outputs_curve_carry_and_funding_signals():
    rows = []
    for idx, date in enumerate(pd.date_range("2026-01-01", periods=25)):
        rows.extend(
            [
                {"date": date, "series_id": "FEDFUNDS", "value": 4.25},
                {"date": date, "series_id": "SOFR", "value": 4.60},
                {"date": date, "series_id": "DGS3MO", "value": 4.40},
                {"date": date, "series_id": "DGS1", "value": 4.30},
                {"date": date, "series_id": "DGS2", "value": 4.00 - idx * 0.01},
                {"date": date, "series_id": "DGS5", "value": 4.10 + idx * 0.02},
                {"date": date, "series_id": "DGS10", "value": 4.20 + idx * 0.01},
                {"date": date, "series_id": "DGS30", "value": 4.50 + idx * 0.005},
            ]
        )
    fred = pd.DataFrame(rows)

    result = build_rates_curve_frame(fred)
    latest = result.iloc[-1]

    assert latest["five_year_two_year_spread"] > 0
    assert latest["ten_year_sofr_carry_proxy"] < 0
    assert latest["sofr_fedfunds_spread"] > 0
    assert latest["funding_pressure_signal"] == "funding_pressure_stress"
    assert latest["belly_signal"] == "belly_stress"
    assert "rates_regime" in result.columns


def test_rates_curve_engine_detects_bull_steepening_from_spread_change():
    rows = []
    for idx, date in enumerate(pd.date_range("2026-01-01", periods=25)):
        rows.extend(
            [
                {"date": date, "series_id": "FEDFUNDS", "value": 3.00},
                {"date": date, "series_id": "SOFR", "value": 3.00},
                {"date": date, "series_id": "DGS3MO", "value": 3.50},
                {"date": date, "series_id": "DGS1", "value": 3.60},
                {"date": date, "series_id": "DGS2", "value": 3.90 - idx * 0.02},
                {"date": date, "series_id": "DGS5", "value": 3.95},
                {"date": date, "series_id": "DGS10", "value": 4.20},
                {"date": date, "series_id": "DGS30", "value": 4.50},
            ]
        )

    result = build_rates_curve_frame(pd.DataFrame(rows))
    latest = result.iloc[-1]

    assert latest["ten_year_two_year_spread_change_20d"] > 0
    assert latest["rates_regime"] == "bull_steepening"


def test_rates_curve_engine_detects_bear_steepening_from_spread_change():
    rows = []
    for idx, date in enumerate(pd.date_range("2026-01-01", periods=25)):
        rows.extend(
            [
                {"date": date, "series_id": "FEDFUNDS", "value": 3.00},
                {"date": date, "series_id": "SOFR", "value": 3.00},
                {"date": date, "series_id": "DGS3MO", "value": 3.50},
                {"date": date, "series_id": "DGS1", "value": 3.60},
                {"date": date, "series_id": "DGS2", "value": 3.80},
                {"date": date, "series_id": "DGS5", "value": 3.90 + idx * 0.005},
                {"date": date, "series_id": "DGS10", "value": 4.10 + idx * 0.02},
                {"date": date, "series_id": "DGS30", "value": 4.50 + idx * 0.005},
            ]
        )

    result = build_rates_curve_frame(pd.DataFrame(rows))
    latest = result.iloc[-1]

    assert latest["ten_year_two_year_spread_change_20d"] > 0
    assert latest["rates_regime"] == "bear_steepening"


def test_rates_curve_engine_uses_same_day_curve_snapshot_and_ignores_official_spreads():
    rows = [
        {"date": "2026-01-01", "series_id": "FEDFUNDS", "value": 3.5},
        {"date": "2026-01-01", "series_id": "SOFR", "value": 3.55},
        {"date": "2026-01-02", "series_id": "DGS3MO", "value": 3.7},
        {"date": "2026-01-02", "series_id": "DGS2", "value": 4.0},
        {"date": "2026-01-02", "series_id": "DGS5", "value": 4.2},
        {"date": "2026-01-02", "series_id": "DGS10", "value": 4.5},
        {"date": "2026-01-02", "series_id": "DGS30", "value": 5.0},
        {"date": "2026-01-02", "series_id": "T10Y2Y", "value": 9.99},
        {"date": "2026-01-02", "series_id": "T10Y3M", "value": 8.88},
        {"date": "2026-01-03", "series_id": "FEDFUNDS", "value": 3.5},
        {"date": "2026-01-03", "series_id": "SOFR", "value": 3.55},
        {"date": "2026-01-03", "series_id": "DGS10", "value": 4.9},
    ]

    result = build_rates_curve_frame(pd.DataFrame(rows))
    latest = result.iloc[-1]

    assert latest["ten_year"] == 4.5
    assert latest["ten_year_two_year_spread"] == pytest.approx(0.5)
    assert latest["ten_year_three_month_spread"] == pytest.approx(0.8)
    assert str(pd.to_datetime(latest["rates_curve_asof_date"]).date()) == "2026-01-02"
    assert latest["ten_year_two_year_spread_fred"] == 9.99


@pytest.mark.parametrize(
    ("sofr_spread", "three_month_spread", "expected"),
    [
        (0.01, 0.10, "funding_pressure_low"),
        (0.06, 0.10, "funding_pressure_mild"),
        (0.10, 0.36, "funding_pressure_elevated"),
        (0.31, 0.10, "funding_pressure_stress"),
    ],
)
def test_rates_curve_engine_funding_pressure_uses_threshold_buckets(sofr_spread, three_month_spread, expected):
    base = 4.0
    rows = [
        {"date": "2026-01-02", "series_id": "FEDFUNDS", "value": base},
        {"date": "2026-01-02", "series_id": "SOFR", "value": base + sofr_spread},
        {"date": "2026-01-02", "series_id": "DGS3MO", "value": base + three_month_spread},
        {"date": "2026-01-02", "series_id": "DGS2", "value": 4.1},
        {"date": "2026-01-02", "series_id": "DGS5", "value": 4.2},
        {"date": "2026-01-02", "series_id": "DGS10", "value": 4.4},
        {"date": "2026-01-02", "series_id": "DGS30", "value": 4.8},
    ]

    result = build_rates_curve_frame(pd.DataFrame(rows))

    assert result.iloc[-1]["funding_pressure_signal"] == expected


def test_rates_curve_engine_belly_signal_uses_relative_20d_move_not_static_level():
    rows = []
    for idx, date in enumerate(pd.date_range("2026-01-01", periods=25)):
        rows.extend(
            [
                {"date": date, "series_id": "FEDFUNDS", "value": 3.00},
                {"date": date, "series_id": "SOFR", "value": 3.00},
                {"date": date, "series_id": "DGS3MO", "value": 3.50},
                {"date": date, "series_id": "DGS1", "value": 3.60},
                {"date": date, "series_id": "DGS2", "value": 3.70 + idx * 0.01},
                {"date": date, "series_id": "DGS5", "value": 4.40 + idx * 0.01},
                {"date": date, "series_id": "DGS10", "value": 4.10 + idx * 0.01},
                {"date": date, "series_id": "DGS30", "value": 4.50 + idx * 0.01},
            ]
        )

    result = build_rates_curve_frame(pd.DataFrame(rows))
    latest = result.iloc[-1]

    assert latest["belly_relative_move"] == pytest.approx(0.0)
    assert latest["belly_signal"] == "belly_normal"
