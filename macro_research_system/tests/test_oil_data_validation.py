import pandas as pd

from src.systems.oil_market.processors.data_validation import (
    validate_eia_frame,
    validate_fred_frame,
    write_data_validation_log,
)
from src.systems.oil_market.fetchers.eia_fetcher import _mock_eia_weekly
from src.systems.oil_market.fetchers.fred_fetcher import _mock_oil_prices
from src.systems.oil_market.processors.oil_market_runner import build_oil_market_summary


def test_fred_validation_flags_linear_ramp_and_sawtooth():
    dates = pd.date_range("2026-01-01", periods=80, freq="B")
    ramp = pd.DataFrame({"date": dates, "wti": range(80), "brent": range(3, 83)})
    saw = pd.DataFrame(
        {
            "date": dates,
            "wti": [70 + (index % 10) for index in range(80)],
            "brent": [73 + (index % 10) for index in range(80)],
        }
    )

    ramp_result = validate_fred_frame(ramp, source_mode="mock")
    saw_result = validate_fred_frame(saw, source_mode="mock")

    assert ramp_result["real_data"] is False
    assert saw_result["real_data"] is False
    assert any("monotonic linear ramp" in item for item in ramp_result["warnings"])
    assert any("repeating sawtooth" in item for item in saw_result["warnings"])


def test_eia_validation_flags_square_wave_fixture():
    dates = pd.date_range("2026-01-01", periods=40, freq="W-FRI")
    frame = pd.DataFrame(
        {
            "date": dates,
            "crude_inventory": [100, 110] * 20,
            "gasoline_inventory": [80, 85] * 20,
            "distillate_inventory": [60, 62] * 20,
            "refinery_utilization": [90, 91] * 20,
            "refinery_crude_inputs": [16000, 16100] * 20,
            "gasoline_product_supplied": [9000, 9100] * 20,
            "distillate_product_supplied": [4000, 4100] * 20,
            "jet_fuel_product_supplied": [1600, 1650] * 20,
            "crude_production": [13000, 13100] * 20,
            "crude_exports": [4500, 4700] * 20,
        }
    )

    result = validate_eia_frame(frame, source_mode="mock")

    assert result["real_data"] is False
    assert any("repeating square wave" in item or "fixed periodic" in item for item in result["warnings"])


def test_eia_validation_flags_inventory_4w_change_fixture_wave():
    dates = pd.date_range("2026-01-01", periods=52, freq="W-FRI")
    inventory = []
    value = 100_000
    for index in range(52):
        if index >= 4:
            value += 500 if index % 2 == 0 else -500
        inventory.append(value)
    frame = pd.DataFrame(
        {
            "date": dates,
            "crude_inventory": inventory,
            "gasoline_inventory": [220_000 + index * 13 for index in range(52)],
            "distillate_inventory": [120_000 + index * 11 for index in range(52)],
            "refinery_utilization": [88 + index * 0.01 for index in range(52)],
            "refinery_crude_inputs": [16_000 + index * 3 for index in range(52)],
            "gasoline_product_supplied": [9_000 + index * 2 for index in range(52)],
            "distillate_product_supplied": [4_000 + index * 2 for index in range(52)],
            "jet_fuel_product_supplied": [1_500 + index * 2 for index in range(52)],
            "crude_production": [13_000 + index * 2 for index in range(52)],
            "crude_exports": [4_500 + index * 2 for index in range(52)],
            "gasoline_crack_proxy": [20 + index * 0.03 for index in range(52)],
            "diesel_crack_proxy": [30 + index * 0.02 for index in range(52)],
        }
    )

    result = validate_eia_frame(frame, source_mode="real")

    assert result["real_data"] is False
    assert any("4W change" in item and "fixed periodic fixture" in item for item in result["warnings"])


def test_eia_validation_flags_crack_spread_linear_ramp_fixture():
    dates = pd.date_range("2026-01-01", periods=52, freq="W-FRI")
    frame = pd.DataFrame(
        {
            "date": dates,
            "crude_inventory": [430_000 + index * 17 for index in range(52)],
            "gasoline_inventory": [220_000 + index * 13 for index in range(52)],
            "distillate_inventory": [120_000 + index * 11 for index in range(52)],
            "refinery_utilization": [88 + index * 0.01 for index in range(52)],
            "refinery_crude_inputs": [16_000 + index * 3 for index in range(52)],
            "gasoline_product_supplied": [9_000 + index * 2 for index in range(52)],
            "distillate_product_supplied": [4_000 + index * 2 for index in range(52)],
            "jet_fuel_product_supplied": [1_500 + index * 2 for index in range(52)],
            "crude_production": [13_000 + index * 2 for index in range(52)],
            "crude_exports": [4_500 + index * 2 for index in range(52)],
            "gasoline_crack_proxy": [15 + index for index in range(52)],
            "diesel_crack_proxy": [25 + index for index in range(52)],
        }
    )

    result = validate_eia_frame(frame, source_mode="real")

    assert result["real_data"] is False
    assert any("crack spread" in item and "linear ramp" in item for item in result["warnings"])


def test_builtin_mock_frames_are_detected_as_fixture_patterns():
    fred_result = validate_fred_frame(_mock_oil_prices(), source_mode="mock")
    eia_result = validate_eia_frame(_mock_eia_weekly(), source_mode="mock")

    assert any("repeating sawtooth" in item or "fixed periodic" in item for item in fred_result["warnings"])
    assert any("repeating sawtooth" in item or "fixed periodic" in item for item in eia_result["warnings"])


def test_mock_summary_forces_mock_data_only_regime():
    dates = pd.date_range("2026-01-01", periods=80, freq="B")
    price = pd.DataFrame({"date": dates, "wti": range(80), "brent": range(3, 83)})
    eia_dates = pd.date_range("2026-01-01", periods=40, freq="W-FRI")
    eia = pd.DataFrame(
        {
            "date": eia_dates,
            "crude_inventory": [100, 110] * 20,
            "gasoline_inventory": [80, 85] * 20,
            "distillate_inventory": [60, 62] * 20,
            "refinery_utilization": [90, 91] * 20,
            "refinery_crude_inputs": [16000, 16100] * 20,
            "gasoline_product_supplied": [9000, 9100] * 20,
            "distillate_product_supplied": [4000, 4100] * 20,
            "jet_fuel_product_supplied": [1600, 1650] * 20,
            "crude_production": [13000, 13100] * 20,
            "crude_exports": [4500, 4700] * 20,
            "gasoline_crack_proxy": [20, 22] * 20,
            "diesel_crack_proxy": [30, 33] * 20,
        }
    )

    summary = build_oil_market_summary(price, eia, ["fixture data used"], fred_source_mode="mock", eia_source_mode="mock")

    assert summary["fred_real_data"] is False
    assert summary["eia_real_data"] is False
    assert summary["mock_mode"] is True
    assert summary["real_data_ready"] is False
    assert summary["data_validation_passed"] is False
    assert summary["oil_regime"] == "mock_data_only"
    assert summary["regime_confidence_score"] <= 10
    assert summary["data_validation_warnings"]


def test_data_validation_log_states_final_pass_status_and_no_warnings(tmp_path):
    path = write_data_validation_log(
        tmp_path,
        {"source": "fred", "real_data": True, "warnings": []},
        {"source": "eia", "real_data": True, "warnings": []},
    )

    text = path.read_text(encoding="utf-8")

    assert "Data validation passed: True" in text
    assert "FRED warnings: none" in text
    assert "EIA warnings: none" in text
