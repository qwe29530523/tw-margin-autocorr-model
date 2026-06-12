import importlib
import json
from pathlib import Path

import pandas as pd

from src.main import main


FORBIDDEN_OIL_TERMS = [
    "Oil",
    "WTI",
    "Brent",
    "crude",
    "gasoline inventory",
    "distillate inventory",
    "refinery",
    "product supplied",
    "crack spread",
    "crude exports",
]

REQUIRED_SUMMARY_KEYS = [
    "system",
    "report_date",
    "data_source_mode",
    "fred_real_data",
    "bls_real_data",
    "mock_mode",
    "real_data_ready",
    "data_validation_passed",
    "rates_asof_date",
    "cpi_asof_month",
    "rates_regime",
    "funding_pressure_signal",
    "carry_signal",
    "curve_signal",
    "cpi_nowcast_signal",
    "fed_funds",
    "sofr",
    "rate_3m",
    "rate_1y",
    "rate_2y",
    "rate_5y",
    "rate_10y",
    "rate_30y",
    "spread_10y_3m",
    "spread_10y_2y",
    "spread_5y_2y",
    "spread_30y_10y",
    "sofr_fed_funds_spread",
    "three_month_fed_funds_spread",
    "headline_cpi_mom_nowcast",
    "headline_cpi_yoy_nowcast",
    "core_cpi_mom_nowcast",
    "core_cpi_yoy_nowcast",
    "data_completeness_score",
    "regime_confidence_score",
    "warnings",
]


def test_rates_cpi_empty_summary_schema():
    from src.systems.rates_cpi.processors.rates_cpi_runner import empty_rates_cpi_summary

    summary = empty_rates_cpi_summary("2026-06-11")

    assert list(summary.keys()) == REQUIRED_SUMMARY_KEYS
    assert summary["system"] == "rates_cpi"
    assert summary["data_source_mode"] == "Core FRED + BLS"
    assert summary["rates_regime"] == "unknown"
    assert summary["warnings"] == []


def test_run_rates_cpi_mock_mode_writes_contract_outputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MOCK_MODE", "true")
    monkeypatch.setenv("FRED_API_KEY", "")
    monkeypatch.setenv("BLS_API_KEY", "")
    monkeypatch.setenv("EIA_API_KEY", "")
    monkeypatch.setattr("sys.argv", ["src.main", "run-rates-cpi"])

    main()

    base = tmp_path / "data" / "rates_cpi"
    summary_path = base / "processed" / "rates_cpi_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    report_path = base / "reports" / f"rates_cpi_report_{summary['report_date'].replace('-', '')}.md"

    assert summary_path.exists()
    assert report_path.exists()
    assert (base / "charts" / "rates_curve.png").exists()
    assert (base / "charts" / "cpi_nowcast.png").exists()
    assert (base / "charts" / "cpi_component_trends.png").exists()
    assert (base / "charts" / "rates_cpi_dashboard.png").exists()
    assert summary["system"] == "rates_cpi"
    assert summary["mock_mode"] is True
    assert summary["real_data_ready"] is False
    assert any("MOCK DATA ONLY" in item for item in summary["warnings"])
    assert "MOCK DATA ONLY" in report_path.read_text(encoding="utf-8")


def test_rates_cpi_report_excludes_oil_terms(tmp_path):
    from src.systems.rates_cpi.processors.rates_cpi_runner import empty_rates_cpi_summary
    from src.systems.rates_cpi.reports.rates_cpi_report import write_rates_cpi_report

    summary = empty_rates_cpi_summary("2026-06-11")
    summary.update({"mock_mode": False, "real_data_ready": True, "data_validation_passed": True})

    path = write_rates_cpi_report(summary, tmp_path)
    text = path.read_text(encoding="utf-8")

    assert "# Rates × CPI Monitor" in text
    for term in FORBIDDEN_OIL_TERMS:
        assert term not in text


def test_rates_cpi_real_mode_requires_valid_fred_and_bls(tmp_path, monkeypatch):
    def fake_fred(settings):
        rows = []
        for series, value in [
            ("FEDFUNDS", 3.90),
            ("SOFR", 3.92),
            ("DGS3MO", 3.80),
            ("DGS1", 3.85),
            ("DGS2", 4.00),
            ("DGS5", 4.15),
            ("DGS10", 4.45),
            ("DGS30", 4.90),
            ("T10Y2Y", 0.45),
            ("T10Y3M", 0.65),
        ]:
            rows.append({"date": "2026-06-05", "series": series, "value": value})
        return pd.DataFrame(rows), [], "real"

    def fake_bls(settings):
        return (
            {
                "energy_proxy_mom": 0.001,
                "gasoline_proxy_mom": 0.001,
                "food_proxy_mom": 0.002,
                "shelter_proxy_mom": 0.003,
                "core_goods_proxy_mom": 0.001,
                "core_services_ex_shelter_proxy_mom": 0.002,
                "cpi_asof_month": "2026-05",
                "component_trends": {
                    "energy_proxy_mom": [{"month": "2026-05", "value": 101.0, "mom": 0.001}],
                    "food_proxy_mom": [{"month": "2026-05", "value": 101.0, "mom": 0.002}],
                    "shelter_proxy_mom": [{"month": "2026-05", "value": 101.0, "mom": 0.003}],
                    "core_goods_proxy_mom": [{"month": "2026-05", "value": 101.0, "mom": 0.001}],
                    "core_services_ex_shelter_proxy_mom": [{"month": "2026-05", "value": 101.0, "mom": 0.002}],
                },
            },
            [],
            "real",
        )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("FRED_API_KEY", "dummy_fred")
    monkeypatch.setenv("BLS_API_KEY", "dummy_bls")
    monkeypatch.setattr("src.systems.rates_cpi.processors.rates_cpi_runner.fetch_fred_rates_frame", fake_fred)
    monkeypatch.setattr("src.systems.rates_cpi.processors.rates_cpi_runner.fetch_bls_cpi_components", fake_bls)
    monkeypatch.setattr("sys.argv", ["src.main", "run-rates-cpi"])

    main()

    path = tmp_path / "data" / "rates_cpi" / "processed" / "rates_cpi_summary.json"
    summary = json.loads(path.read_text(encoding="utf-8"))

    assert summary["fred_real_data"] is True
    assert summary["bls_real_data"] is True
    assert summary["mock_mode"] is False
    assert summary["real_data_ready"] is True
    assert summary["data_validation_passed"] is True


def test_rates_cpi_package_does_not_import_oil_systems():
    package_root = Path(__file__).resolve().parents[1] / "src" / "systems" / "rates_cpi"

    for path in package_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "src.systems.oil_market" not in text
        assert "src.systems.oil_rates_cpi" not in text


def test_legacy_oil_rates_cpi_remains_available():
    module = importlib.import_module("src.systems.oil_rates_cpi.processors.macro_regime_engine")

    assert hasattr(module, "run_oil_rates_cpi")


def test_backtest_cpi_writes_rates_cpi_backtest_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["src.main", "backtest-cpi", "--start", "2018-01", "--end", "2026-05"])

    main()

    path = tmp_path / "data" / "rates_cpi" / "backtests" / "cpi_nowcast_backtest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["system"] == "rates_cpi"
    assert payload["backtest"] == "cpi_nowcast"
    assert payload["start"] == "2018-01"
    assert payload["end"] == "2026-05"
