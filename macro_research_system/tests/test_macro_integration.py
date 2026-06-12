import json
from pathlib import Path

from src.main import main
from src.systems.macro_integration.integrated_report import write_integrated_report
from src.systems.macro_integration.regime_matrix import DEFAULT_ALLOCATION_VIEW, SUMMARY_KEYS, integrate_regimes
from src.systems.macro_integration.signal_adapter import load_system_summaries


def tw_summary(
    final_signal="NORMAL",
    phase="normal",
    risk_level="low",
    ready=True,
    margin_signal="stable",
):
    return {
        "system": "tw_margin_cycle",
        "final_signal": final_signal,
        "leverage_cycle_phase": phase,
        "risk_level": risk_level,
        "margin_cycle_signal": margin_signal,
        "data_validation_passed": ready,
        "mock_mode": not ready,
    }


def oil_summary(
    regime="neutral_mixed",
    momentum="neutral",
    inventory="neutral",
    product_demand="neutral",
    supply="neutral",
    ready=True,
):
    return {
        "system": "oil_market",
        "oil_regime": regime,
        "oil_momentum_signal": momentum,
        "inventory_signal": inventory,
        "product_demand_signal": product_demand,
        "supply_signal": supply,
        "price_war_risk": False,
        "supply_shock_risk": regime == "supply_shock",
        "demand_destruction_risk": False,
        "real_data_ready": ready,
        "data_validation_passed": ready,
        "mock_mode": not ready,
    }


def rates_summary(
    regime="neutral",
    funding="funding_pressure_low",
    carry="carry_positive",
    curve="neutral",
    cpi="disinflationary",
    ready=True,
):
    return {
        "system": "rates_cpi",
        "rates_regime": regime,
        "funding_pressure_signal": funding,
        "carry_signal": carry,
        "curve_signal": curve,
        "cpi_nowcast_signal": cpi,
        "real_data_ready": ready,
        "data_validation_passed": ready,
        "mock_mode": not ready,
    }


def test_integration_summary_schema_defaults():
    result = integrate_regimes({}, {}, {})

    assert list(result.keys()) == SUMMARY_KEYS
    assert result["system"] == "macro_integration"
    assert result["tw_margin_system_ready"] is False
    assert result["oil_market_system_ready"] is False
    assert result["rates_cpi_system_ready"] is False
    assert result["asset_allocation_view"] == DEFAULT_ALLOCATION_VIEW
    assert result["final_market_state"] == "neutral_mixed"


def test_load_system_summaries_reads_abc_only_and_ignores_legacy(tmp_path):
    data_root = tmp_path / "data"
    tw_path = data_root / "tw_margin_cycle" / "processed"
    oil_path = data_root / "oil_market" / "processed"
    rates_path = data_root / "rates_cpi" / "processed"
    legacy_path = data_root / "oil_rates_cpi" / "processed"
    for path in [tw_path, oil_path, rates_path, legacy_path]:
        path.mkdir(parents=True)
    (tw_path / "tw_margin_cycle_summary.json").write_text(json.dumps(tw_summary()), encoding="utf-8")
    (oil_path / "oil_market_summary.json").write_text(json.dumps(oil_summary()), encoding="utf-8")
    (rates_path / "rates_cpi_summary.json").write_text(json.dumps(rates_summary()), encoding="utf-8")
    (legacy_path / "oil_rates_cpi_summary.json").write_text(
        json.dumps({"system": "oil_rates_cpi", "rates_regime": "legacy_should_not_be_read"}),
        encoding="utf-8",
    )

    tw, oil, rates, warnings = load_system_summaries(data_root)

    assert tw["system"] == "tw_margin_cycle"
    assert oil["system"] == "oil_market"
    assert rates["system"] == "rates_cpi"
    assert rates["rates_regime"] != "legacy_should_not_be_read"
    assert warnings == []


def test_missing_one_subsystem_summary_warns_without_crashing(tmp_path):
    data_root = tmp_path / "data"
    (data_root / "tw_margin_cycle" / "processed").mkdir(parents=True)
    (data_root / "oil_market" / "processed").mkdir(parents=True)
    (data_root / "tw_margin_cycle" / "processed" / "tw_margin_cycle_summary.json").write_text(
        json.dumps(tw_summary()),
        encoding="utf-8",
    )
    (data_root / "oil_market" / "processed" / "oil_market_summary.json").write_text(
        json.dumps(oil_summary()),
        encoding="utf-8",
    )

    tw, oil, rates, warnings = load_system_summaries(data_root)
    result = integrate_regimes(tw, oil, rates)
    result["warnings"].extend(warnings)

    assert result["rates_cpi_system_ready"] is False
    assert any("Rates x CPI summary missing" in warning for warning in warnings)
    assert result["final_market_state"] == "neutral_mixed"


def test_integration_late_cycle_but_bond_supported_rule():
    result = integrate_regimes(
        tw_summary(final_signal="LATE_CYCLE_LEVERAGE_WARNING", phase="late_cycle_leverage_warning", risk_level="high"),
        oil_summary(regime="neutral_mixed"),
        rates_summary(regime="neutral", carry="carry_positive", cpi="disinflationary"),
    )

    assert result["final_market_state"] == "late_cycle_but_bond_supported"
    assert result["bond_support_score"] > result["inflation_risk_score"]


def test_integration_late_cycle_with_inflation_pressure_rule():
    result = integrate_regimes(
        tw_summary(final_signal="LATE_CYCLE_LEVERAGE_WARNING", phase="late_cycle_leverage_warning", risk_level="high"),
        oil_summary(regime="demand_led_strength"),
        rates_summary(regime="neutral", cpi="inflationary"),
    )

    assert result["final_market_state"] == "late_cycle_with_inflation_pressure"
    assert result["inflation_risk_score"] >= 70


def test_integration_overheat_with_rate_pressure_rule():
    result = integrate_regimes(
        tw_summary(final_signal="LATE_CYCLE_LEVERAGE_WARNING", phase="late_cycle_leverage_warning", risk_level="high"),
        oil_summary(regime="neutral_mixed"),
        rates_summary(
            regime="macro_tightening",
            funding="funding_pressure_elevated",
            curve="partial_inversion",
            cpi="inflationary",
        ),
    )

    assert result["final_market_state"] == "overheat_with_rate_pressure"
    assert result["macro_tightening_score"] >= 70


def test_integration_stagflation_late_cycle_risk_rule():
    result = integrate_regimes(
        tw_summary(final_signal="LATE_CYCLE_LEVERAGE_WARNING", phase="late_cycle_leverage_warning", risk_level="high"),
        oil_summary(regime="supply_led_tightness"),
        rates_summary(regime="macro_tightening", carry="carry_negative", cpi="inflationary"),
    )

    assert result["final_market_state"] == "stagflation_late_cycle_risk"
    assert result["commodity_pressure_score"] >= 70


def test_integration_deleveraging_pressure_rule():
    result = integrate_regimes(
        tw_summary(final_signal="DELEVERAGING_RISK", phase="deleveraging_risk", risk_level="high", margin_signal="weakening"),
        oil_summary(regime="neutral_mixed"),
        rates_summary(cpi="disinflationary"),
    )

    assert result["final_market_state"] == "deleveraging_pressure"
    assert result["deleveraging_risk_score"] >= 80


def test_integration_warns_when_system_b_or_c_not_ready():
    result = integrate_regimes(
        tw_summary(),
        oil_summary(ready=False),
        rates_summary(ready=False),
    )

    assert result["oil_market_system_ready"] is False
    assert result["rates_cpi_system_ready"] is False
    assert any("System B oil_market is not real-data ready" in warning for warning in result["warnings"])
    assert any("System C rates_cpi is not real-data ready" in warning for warning in result["warnings"])


def test_integrated_report_uses_system_d_sections(tmp_path):
    summary = integrate_regimes(tw_summary(), oil_summary(), rates_summary())

    path = write_integrated_report(summary, tmp_path)
    report = path.read_text(encoding="utf-8")

    assert "# Integrated Macro Monitor" in report
    for section in [
        "## 今日總結",
        "## System A：TW Margin × Index Growth",
        "## System B：Crude Oil Market",
        "## System C：Rates × CPI",
        "## Cross-system interpretation",
        "## Asset allocation view",
        "## Warnings",
    ]:
        assert section in report


def test_run_integrated_writes_contract_outputs(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    for relative, payload in [
        ("tw_margin_cycle/processed/tw_margin_cycle_summary.json", tw_summary()),
        ("oil_market/processed/oil_market_summary.json", oil_summary()),
        ("rates_cpi/processed/rates_cpi_summary.json", rates_summary()),
        ("oil_rates_cpi/processed/oil_rates_cpi_summary.json", {"system": "oil_rates_cpi", "rates_regime": "legacy"}),
    ]:
        path = data_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["src.main", "run-integrated"])

    main()

    summary_path = data_root / "integrated" / "processed" / "integrated_macro_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    assert summary["system"] == "macro_integration"
    assert summary["rates_regime"] != "legacy"
    assert (data_root / "integrated" / "reports" / f"integrated_macro_report_{summary['report_date'].replace('-', '')}.md").exists()
    assert (data_root / "integrated" / "charts").exists()


def test_run_all_order_excludes_legacy_oil_rates_cpi(monkeypatch, tmp_path):
    calls = []

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("src.main.run_tw_margin_cycle", lambda data_root: calls.append("run-tw-margin"))
    monkeypatch.setattr("src.main.run_oil_market", lambda data_root: calls.append("run-oil-market"))
    monkeypatch.setattr("src.main.run_rates_cpi", lambda data_root: calls.append("run-rates-cpi"))
    monkeypatch.setattr("src.main.run_oil_rates_cpi", lambda data_root: calls.append("run-oil-rates-cpi"))
    monkeypatch.setattr("src.main.run_integrated", lambda data_root: calls.append("run-integrated"))
    monkeypatch.setattr("sys.argv", ["src.main", "run-all"])

    main()

    assert calls == ["run-tw-margin", "run-oil-market", "run-rates-cpi", "run-integrated"]
