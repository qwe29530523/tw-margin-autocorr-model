from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.systems.oil_market.calculate_cftc_oil_positioning import calculate_oil_positioning_squeeze


FORBIDDEN_COLUMNS = {
    "production_score",
    "composite_score",
    "final_trading_signal",
    "trading_signal",
}


def _cot_fixture() -> pd.DataFrame:
    dates = pd.date_range("2026-01-02", periods=8, freq="W-FRI")
    return pd.DataFrame(
        {
            "date": dates,
            "market": ["WTI_CRUDE_OIL"] * len(dates),
            "managed_money_long": [120, 118, 116, 114, 112, 110, 112, 130],
            "managed_money_short": [60, 70, 80, 90, 105, 125, 145, 150],
            "open_interest": [1000] * len(dates),
        }
    )


def test_calculate_oil_positioning_squeeze_computes_net_percent_oi_and_changes() -> None:
    result = calculate_oil_positioning_squeeze(_cot_fixture(), lookback_weeks=8)
    latest = result.iloc[-1]

    assert latest["managed_money_net"] == -20
    assert latest["managed_money_net_percent_oi"] == -0.02
    assert latest["managed_money_short_percent_oi"] == 0.15
    assert latest["managed_money_1w_change"] == 13
    assert latest["managed_money_7w_change"] == -80
    assert 0 <= latest["managed_money_net_percentile"] <= 1
    assert 0 <= latest["managed_money_short_percentile"] <= 1
    assert set(result["source_name"]) == {"CFTC_COT"}
    assert set(result["source_type"]) == {"official_public_positioning_data"}
    assert FORBIDDEN_COLUMNS.isdisjoint(result.columns)


def test_positioning_state_identifies_crowded_short_without_final_signal() -> None:
    result = calculate_oil_positioning_squeeze(_cot_fixture(), lookback_weeks=8)

    assert result.iloc[-1]["oil_positioning_state"] in {
        "CROWDED_SHORT",
        "EXTREME_CROWDED_SHORT",
        "SHORT_SQUEEZE_SETUP_CANDIDATE",
    }
    assert result.iloc[-1]["oil_squeeze_risk"] in {"ELEVATED", "HIGH"}
    assert "final_trading_signal" not in result.columns


def test_missing_required_positioning_values_returns_missing_state() -> None:
    frame = _cot_fixture()
    frame.loc[frame.index[-1], "open_interest"] = 0

    result = calculate_oil_positioning_squeeze(frame, lookback_weeks=8)
    latest = result.iloc[-1]

    assert pd.isna(latest["managed_money_net_percent_oi"])
    assert pd.isna(latest["managed_money_short_percent_oi"])
    assert latest["oil_positioning_state"] == "MISSING"
    assert latest["oil_squeeze_risk"] == "MISSING"


def test_cftc_positioning_needs_no_api_key_or_file_writes(monkeypatch, tmp_path: Path) -> None:
    def fail_getenv(*args, **kwargs):  # pragma: no cover - called only on failure
        raise AssertionError("CFTC positioning calculator must not read .env or environment variables")

    monkeypatch.setattr("os.getenv", fail_getenv)
    before = set(tmp_path.iterdir())

    result = calculate_oil_positioning_squeeze(_cot_fixture(), lookback_weeks=8)

    assert not result.empty
    assert set(tmp_path.iterdir()) == before
    assert "api-key-dummy-value" not in result.to_string()
