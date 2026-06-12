from src.systems.oil_rates_cpi.processors.macro_regime_engine import build_oil_rates_cpi_summary


def test_macro_regime_summary_schema_contains_cpi_and_rates_fields():
    summary = build_oil_rates_cpi_summary(mock_mode=True)

    assert summary["system"] == "oil_rates_cpi"
    assert "cpi_nowcast_signal" in summary
    assert "funding_pressure_signal" in summary
    assert "warnings" in summary
