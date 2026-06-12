import json

import pandas as pd

from src.systems.oil_market.charts.oil_crack_spread_chart import write_oil_crack_spread_chart
from src.systems.oil_market.backtests.oil_regime_backtest import run_oil_regime_backtest
from src.systems.oil_market.processors.oil_market_runner import build_oil_market_summary
from src.systems.oil_market.processors.oil_regime_engine import SUMMARY_KEYS, empty_oil_summary
from src.systems.oil_market.processors.oil_market_runner import run_oil_market
from src.systems.oil_market.reports.oil_market_report import write_oil_market_report


FORBIDDEN_MACRO_TERMS = ["CPI", "rates", "funding", "carry", "yield curve", "10Y-3M", "10Y-2Y"]


def test_oil_market_report_writes_required_sections(tmp_path):
    summary = empty_oil_summary("2026-06-09")
    summary.update(
        {
            "oil_regime": "tight_inventory_weak_products",
            "regime_confidence_score": 57,
            "real_data_ready": True,
            "warnings": ["test warning"],
        }
    )

    path = write_oil_market_report(summary, tmp_path)
    text = path.read_text(encoding="utf-8")

    assert "# Crude Oil Market Monitor" in text
    assert "## 1. 今日總結" in text
    assert "## 8. Warnings" in text
    assert "tight_inventory_weak_products" in text


def test_oil_market_report_formats_eia_units_as_millions(tmp_path):
    summary = empty_oil_summary("2026-06-09")
    summary.update(
        {
            "real_data_ready": True,
            "oil_regime": "neutral_mixed",
            "regime_confidence_score": 61,
            "crude_inventory_4w_change": -23470.0,
            "gasoline_product_supplied_4w_change": -219.0,
            "crude_exports": 5874.0,
            "warnings": [],
        }
    )

    path = write_oil_market_report(summary, tmp_path)
    text = path.read_text(encoding="utf-8")

    assert "- crude inventory 4W change: -23.47 million barrels" in text
    assert "- gasoline product supplied 4W change: -0.22 million barrels/day" in text
    assert "- crude exports: 5.87 million barrels/day" in text


def test_mock_oil_market_report_suppresses_formal_subsignals(tmp_path):
    summary = empty_oil_summary("2026-06-09")
    summary.update(
        {
            "data_source_mode": "MOCK DATA ONLY — NOT FOR MARKET INTERPRETATION",
            "real_data_ready": False,
            "data_validation_passed": False,
            "oil_regime": "mock_data_only",
            "regime_confidence_score": 10,
            "oil_momentum_signal": "oil_up_medium_term",
            "inventory_signal": "inventory_tightening",
            "product_demand_signal": "broad_product_demand_strength",
            "data_validation_warnings": ["FRED source mode is not real API data."],
            "warnings": ["MOCK DATA ONLY — NOT FOR MARKET INTERPRETATION"],
        }
    )

    path = write_oil_market_report(summary, tmp_path)
    text = path.read_text(encoding="utf-8")

    assert "MOCK DATA ONLY — NOT FOR MARKET INTERPRETATION" in text
    assert "Formal market interpretation: disabled" in text
    for section in [
        "## 1. 今日總結",
        "## 2. 油價",
        "## 3. 庫存",
        "## 4. 成品需求",
        "## 5. 裂解價差",
        "## 6. 煉廠與供給",
        "## 7. 原油市場解讀",
        "## 8. Warnings",
    ]:
        assert section in text
    for forbidden in FORBIDDEN_MACRO_TERMS:
        assert forbidden not in text


def test_real_oil_market_report_omits_mixed_macro_terms(tmp_path):
    summary = empty_oil_summary("2026-06-09")
    summary.update(
        {
            "real_data_ready": True,
            "data_validation_passed": True,
            "oil_regime": "neutral_mixed",
            "regime_confidence_score": 70,
            "warnings": [],
        }
    )

    path = write_oil_market_report(summary, tmp_path)
    text = path.read_text(encoding="utf-8")

    assert "# Crude Oil Market Monitor" in text
    assert "MOCK DATA ONLY" not in text
    for forbidden in FORBIDDEN_MACRO_TERMS:
        assert forbidden not in text


def test_run_oil_market_mock_mode_does_not_crash_and_writes_schema(tmp_path, monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "")
    monkeypatch.setenv("EIA_API_KEY", "")
    monkeypatch.setenv("BLS_API_KEY", "")
    monkeypatch.setenv("MOCK_MODE", "true")

    summary = run_oil_market(tmp_path)
    summary_path = tmp_path / "oil_market" / "processed" / "oil_market_summary.json"

    assert summary["system"] == "oil_market"
    assert summary_path.exists()
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["system"] == "oil_market"
    assert payload["oil_regime"] == "mock_data_only"
    assert payload["regime_confidence_score"] <= 10
    assert payload["data_source_mode"] == "Core FRED + EIA"
    assert list(payload.keys()) == SUMMARY_KEYS
    assert list(summary.keys()) == SUMMARY_KEYS
    assert "curve_state" not in payload
    assert "futures_curve_warning" not in payload
    warning_text = "\n".join(payload["warnings"])
    assert ".env loaded:" in warning_text
    assert "MOCK_MODE actual value: true" in warning_text
    assert "FRED_API_KEY present: false" in warning_text
    assert "EIA_API_KEY present: false" in warning_text
    assert "FRED request success: false" in warning_text
    assert "EIA request success: false" in warning_text
    for forbidden in ["BLS", *FORBIDDEN_MACRO_TERMS]:
        assert forbidden not in warning_text


def test_run_oil_market_real_fetch_success_sets_real_data_ready(tmp_path, monkeypatch):
    monkeypatch.delenv("BLS_API_KEY", raising=False)
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("FRED_API_KEY", "fred-secret-value")
    monkeypatch.setenv("EIA_API_KEY", "eia-secret-value")
    dates = pd.date_range("2026-01-01", periods=90, freq="B")
    price = pd.DataFrame(
        {
            "date": dates,
            "wti": [70 + index * 0.05 + (index % 7) * 0.11 for index in range(90)],
            "brent": [73 + index * 0.05 + (index % 5) * 0.13 for index in range(90)],
        }
    )
    eia_dates = pd.date_range("2026-01-02", periods=52, freq="W-FRI")
    eia = pd.DataFrame(
        {
            "date": eia_dates,
            "crude_inventory": [430000 + index * 31 + index * index * 2 + (index % 5) * 47 for index in range(52)],
            "gasoline_inventory": [220000 + index * 19 + index * index * 3 + (index % 7) * 29 for index in range(52)],
            "distillate_inventory": [120000 + index * 17 + index * index * 2.5 + (index % 6) * 23 for index in range(52)],
            "refinery_utilization": [86 + (index % 9) * 0.37 + index * 0.01 for index in range(52)],
            "refinery_crude_inputs": [15800 + index * 11 + (index % 4) * 17 for index in range(52)],
            "crude_production": [12800 + index * 9 + (index % 8) * 13 for index in range(52)],
            "crude_exports": [3900 + index * 7 + (index % 10) * 31 for index in range(52)],
            "gasoline_product_supplied": [8800 + index * 5 + (index % 6) * 17 for index in range(52)],
            "distillate_product_supplied": [4000 + index * 4 + (index % 5) * 19 for index in range(52)],
            "jet_fuel_product_supplied": [1500 + index * 3 + (index % 7) * 11 for index in range(52)],
            "gasoline_crack_proxy": [18 + index * 0.07 + (index % 6) * 0.17 for index in range(52)],
            "diesel_crack_proxy": [24 + index * 0.08 + (index % 5) * 0.19 for index in range(52)],
        }
    )

    monkeypatch.setattr(
        "src.systems.oil_market.processors.oil_market_runner.fetch_oil_price_frame",
        lambda settings: (price, ["FRED request success: true; series: DCOILWTICO,DCOILBRENTEU."], "real"),
    )
    monkeypatch.setattr(
        "src.systems.oil_market.processors.oil_market_runner.fetch_eia_oil_frame",
        lambda settings: (eia, ["EIA request success: true; weekly petroleum series loaded."], "real"),
    )

    summary = run_oil_market(tmp_path)

    assert summary["mock_mode"] is False
    assert summary["fred_real_data"] is True
    assert summary["eia_real_data"] is True
    assert summary["real_data_ready"] is True
    assert summary["data_validation_passed"] is True
    warning_text = "\n".join(summary["warnings"])
    assert "FRED_API_KEY present: true" in warning_text
    assert "EIA_API_KEY present: true" in warning_text
    assert "fred-secret-value" not in warning_text
    assert "eia-secret-value" not in warning_text


def test_oil_market_output_contract_paths_are_stable(tmp_path, monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "")
    monkeypatch.setenv("EIA_API_KEY", "")
    monkeypatch.setenv("BLS_API_KEY", "")
    monkeypatch.setenv("MOCK_MODE", "true")

    summary = run_oil_market(tmp_path)
    run_oil_regime_backtest("2018-01-01", "2026-06-08", tmp_path / "oil_market" / "backtests")
    report_date = summary["report_date"].replace("-", "")

    expected_paths = [
        tmp_path / "oil_market" / "processed" / "oil_market_summary.json",
        tmp_path / "oil_market" / "reports" / f"oil_market_report_{report_date}.md",
        tmp_path / "oil_market" / "charts" / "oil_price_momentum.png",
        tmp_path / "oil_market" / "charts" / "oil_inventory_proxy.png",
        tmp_path / "oil_market" / "charts" / "oil_product_demand.png",
        tmp_path / "oil_market" / "charts" / "oil_crack_spread.png",
        tmp_path / "oil_market" / "charts" / "oil_market_dashboard.png",
        tmp_path / "oil_market" / "backtests" / "oil_regime_backtest.json",
    ]

    for path in expected_paths:
        assert path.exists(), path


def test_oil_market_summary_rounds_numeric_values_for_json():
    dates = pd.date_range("2026-01-01", periods=90, freq="B")
    price = pd.DataFrame(
        {
            "date": dates,
            "wti": [70.0 + index * 0.01 for index in range(89)] + [95.0],
            "brent": [72.0 + index * 0.01 for index in range(89)] + [97.46],
        }
    )
    eia_dates = pd.date_range("2026-01-02", periods=52, freq="W-FRI")
    eia = pd.DataFrame(
        {
            "date": eia_dates,
            "crude_inventory": [430000 + index * 31 + index * index * 2 + (index % 5) * 47 for index in range(52)],
            "gasoline_inventory": [220000 + index * 19 + index * index * 3 + (index % 7) * 29 for index in range(52)],
            "distillate_inventory": [120000 + index * 17 + index * index * 2.5 + (index % 6) * 23 for index in range(52)],
            "refinery_utilization": [86 + (index % 9) * 0.37 + index * 0.01 for index in range(52)],
            "refinery_crude_inputs": [15800 + index * 11 + (index % 4) * 17 for index in range(52)],
            "crude_production": [12800 + index * 9 + (index % 8) * 13 for index in range(52)],
            "crude_exports": [3900 + index * 7 + (index % 10) * 31 for index in range(52)],
            "gasoline_product_supplied": [8800 + index * 5 + (index % 6) * 17 for index in range(52)],
            "distillate_product_supplied": [4000 + index * 4 + (index % 5) * 19 for index in range(52)],
            "jet_fuel_product_supplied": [1500 + index * 3 + (index % 7) * 11 for index in range(52)],
            "gasoline_crack_proxy": [18 + index * 0.07 + (index % 6) * 0.17 for index in range(52)],
            "diesel_crack_proxy": [24 + index * 0.08 + (index % 5) * 0.19 for index in range(52)],
        }
    )

    summary = build_oil_market_summary(price, eia, [], fred_source_mode="real", eia_source_mode="real")

    assert summary["brent_wti_spread"] == 2.46
    assert summary["wti_return_5d"] == round(summary["wti_return_5d"], 6)


def test_mock_crack_spread_chart_marks_title(tmp_path, monkeypatch):
    titles = []

    def capture_title(self, label, *args, **kwargs):
        titles.append(label)
        return original_set_title(self, label, *args, **kwargs)

    import matplotlib.axes

    original_set_title = matplotlib.axes.Axes.set_title
    monkeypatch.setattr(matplotlib.axes.Axes, "set_title", capture_title)
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=25, freq="W-FRI"),
            "gasoline_crack_proxy": range(25),
            "diesel_crack_proxy": range(10, 35),
        }
    )

    output = write_oil_crack_spread_chart(frame, tmp_path / "oil_crack_spread.png", mock_data_only=True)

    assert output.exists()
    assert any(title.startswith("[MOCK DATA ONLY]") for title in titles)
