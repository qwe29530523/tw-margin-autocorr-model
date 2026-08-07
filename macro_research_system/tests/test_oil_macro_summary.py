from __future__ import annotations

import builtins
import os
import socket
from pathlib import Path

import pandas as pd

from src.systems.oil_market.build_oil_macro_summary import (
    build_oil_macro_summary,
    classify_crack_spread_proxy_trend,
)


FORBIDDEN_FIELDS = {
    "production_score",
    "composite_score",
    "final_trading_signal",
    "buy_signal",
    "sell_signal",
}

EXPECTED_KEYS = {
    "module_name",
    "as_of_date",
    "data_status",
    "oil_rate_mix",
    "oil_physical_tightness",
    "product_inventory_pressure",
    "crack_spread_proxy_status",
    "gasoline_crack_research_proxy_trend",
    "distillate_crack_research_proxy_trend",
    "crack_321_research_proxy_trend",
    "oil_positioning_state",
    "oil_squeeze_risk",
    "wti_curve_status",
    "primary_oil_macro_regime",
    "confidence",
    "risk_level",
    "drivers",
    "warning_flags",
    "next_watch_items",
    "data_caveats",
}


def _oil_rate_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-06-07", "2026-06-14"]),
            "oil_rate_mix": ["MIXED", "OIL_PRESSURE"],
        }
    )


def _physical_df(tightness: str = "PHYSICAL_TIGHT") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-06-07", "2026-06-14"]),
            "oil_physical_tightness": ["MIXED", tightness],
            "product_inventory_pressure": ["MIXED", "PRODUCT_TIGHTNESS"],
        }
    )


def _crack_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-06-10", "2026-06-11", "2026-06-12"]),
            "gasoline_crack_research_proxy": [18.0, float("nan"), 22.0],
            "distillate_crack_research_proxy": [24.0, 25.0, 28.0],
            "crack_321_research_proxy": [20.0, 21.0, 25.0],
            "source_type": ["research_only_public_proxy"] * 3,
            "data_status": ["RESEARCH_ONLY"] * 3,
            "caveat": ["yfinance research-only crack spread proxy"] * 3,
        }
    )


def _positioning_df(state: str = "CROWDED_SHORT", risk: str = "HIGH") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-06-07", "2026-06-14"]),
            "oil_positioning_state": ["POSITIONING_NEUTRAL", state],
            "oil_squeeze_risk": ["LOW", risk],
            "source_type": ["official_public_positioning_data"] * 2,
            "data_status": ["PUBLIC_DATA_SOURCE"] * 2,
            "caveat": ["CFTC positioning diagnostics only"] * 2,
        }
    )


def _coverage_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "mapped_field": "gasoline_crack_research_proxy",
                "source_type": "research_only_public_proxy",
                "status": "RESEARCH_ONLY",
                "caveat": "yfinance crack spread is research-only",
                "is_available": True,
            },
            {
                "mapped_field": "oil_positioning_squeeze_state",
                "source_type": "official_public_positioning_data",
                "status": "PUBLIC_DATA_SOURCE",
                "caveat": "CFTC positioning diagnostics only",
                "is_available": True,
            },
            {
                "mapped_field": "wti_m1_m2_m3_curve",
                "source_type": "official_exchange_or_licensed_vendor_required",
                "status": "BLOCKED_VENDOR_NOT_CONFIGURED",
                "caveat": "WTI M1/M2/M3 futures curve blocker remains open",
                "is_available": False,
            },
        ]
    )


def test_build_oil_macro_summary_returns_expected_keys() -> None:
    summary = build_oil_macro_summary(
        oil_rate_df=_oil_rate_df(),
        physical_df=_physical_df(),
        crack_spread_research_df=_crack_df(),
        positioning_df=_positioning_df(),
        coverage_df=_coverage_df(),
    )

    assert EXPECTED_KEYS <= set(summary)
    assert summary["module_name"] == "oil_macro_core"
    assert summary["wti_curve_status"] == "BLOCKED_VENDOR_NOT_CONFIGURED"
    assert FORBIDDEN_FIELDS.isdisjoint(summary)


def test_physical_tight_with_supportive_crack_proxy_returns_supported_regime() -> None:
    summary = build_oil_macro_summary(
        oil_rate_df=_oil_rate_df(),
        physical_df=_physical_df(),
        crack_spread_research_df=_crack_df(),
        coverage_df=_coverage_df(),
    )

    assert summary["primary_oil_macro_regime"] == "PHYSICAL_TIGHT_WITH_RESEARCH_PROXY_SUPPORT"
    assert summary["crack_spread_proxy_status"] == "RESEARCH_ONLY"
    assert summary["gasoline_crack_research_proxy_trend"] == "UP"


def test_physical_tight_with_missing_crack_and_blocked_curve_returns_blocked_regime() -> None:
    summary = build_oil_macro_summary(
        oil_rate_df=_oil_rate_df(),
        physical_df=_physical_df(),
        crack_spread_research_df=None,
        coverage_df=_coverage_df(),
    )

    assert summary["primary_oil_macro_regime"] == "PHYSICAL_TIGHT_BUT_CURVE_BLOCKED"
    assert summary["crack_spread_proxy_status"] == "MISSING"
    assert "WTI_CURVE_BLOCKED_VENDOR_NOT_CONFIGURED" in summary["warning_flags"]


def test_crowded_short_high_squeeze_risk_returns_research_proxy_positioning_candidate() -> None:
    summary = build_oil_macro_summary(
        oil_rate_df=pd.DataFrame({"date": ["2026-06-14"], "oil_rate_mix": ["MIXED"]}),
        physical_df=pd.DataFrame(
            {
                "date": ["2026-06-14"],
                "oil_physical_tightness": ["MIXED"],
                "product_inventory_pressure": ["MIXED"],
            }
        ),
        positioning_df=_positioning_df("EXTREME_CROWDED_SHORT", "HIGH"),
        coverage_df=_coverage_df(),
    )

    assert summary["primary_oil_macro_regime"] == "RESEARCH_PROXY_POSITIONING_SQUEEZE_CANDIDATE"
    assert "final_trading_signal" not in summary
    assert "CFTC_POSITIONING_DIAGNOSTICS_ONLY" in summary["warning_flags"]


def test_missing_all_inputs_returns_missing_status_and_regime() -> None:
    summary = build_oil_macro_summary()

    assert summary["primary_oil_macro_regime"] == "MISSING_OIL_MACRO_DATA"
    assert summary["data_status"] == "MISSING"
    assert summary["risk_level"] == "UNKNOWN"


def test_yfinance_caveat_is_preserved() -> None:
    summary = build_oil_macro_summary(crack_spread_research_df=_crack_df(), coverage_df=_coverage_df())

    assert any("yfinance" in caveat for caveat in summary["data_caveats"])
    assert "CRACK_SPREAD_RESEARCH_PROXY_ONLY" in summary["warning_flags"]


def test_cftc_positioning_caveat_is_preserved() -> None:
    summary = build_oil_macro_summary(positioning_df=_positioning_df(), coverage_df=_coverage_df())

    assert any("CFTC" in caveat for caveat in summary["data_caveats"])
    assert "CFTC_POSITIONING_DIAGNOSTICS_ONLY" in summary["warning_flags"]


def test_wti_m1_m2_m3_blocker_remains_open() -> None:
    summary = build_oil_macro_summary(coverage_df=_coverage_df())

    assert summary["wti_curve_status"] == "BLOCKED_VENDOR_NOT_CONFIGURED"
    assert any("WTI M1/M2/M3" in item for item in summary["next_watch_items"])


def test_no_forbidden_fields_are_created() -> None:
    summary = build_oil_macro_summary(
        oil_rate_df=_oil_rate_df(),
        physical_df=_physical_df(),
        crack_spread_research_df=_crack_df(),
        positioning_df=_positioning_df(),
        coverage_df=_coverage_df(),
    )

    assert FORBIDDEN_FIELDS.isdisjoint(summary)
    assert "production_score" not in str(summary)
    assert "composite_score" not in str(summary)
    assert "final_trading_signal" not in str(summary)


def test_no_api_call(monkeypatch) -> None:
    def fail_network(*_args, **_kwargs):
        raise AssertionError("network call attempted")

    monkeypatch.setattr(socket, "create_connection", fail_network)

    summary = build_oil_macro_summary(oil_rate_df=_oil_rate_df())

    assert summary["module_name"] == "oil_macro_core"


def test_no_env_read(monkeypatch) -> None:
    def fail_getenv(*_args, **_kwargs):
        raise AssertionError(".env or environment read attempted")

    monkeypatch.setattr(os, "getenv", fail_getenv)

    summary = build_oil_macro_summary(physical_df=_physical_df())

    assert summary["oil_physical_tightness"] == "PHYSICAL_TIGHT"


def test_no_file_writes(monkeypatch, tmp_path: Path) -> None:
    before = set(tmp_path.iterdir())

    def guarded_open(file, mode="r", *args, **kwargs):
        if any(flag in mode for flag in ("w", "a", "x", "+")):
            raise AssertionError("file write attempted")
        return original_open(file, mode, *args, **kwargs)

    original_open = builtins.open
    monkeypatch.setattr(builtins, "open", guarded_open)

    summary = build_oil_macro_summary(crack_spread_research_df=_crack_df())

    assert set(tmp_path.iterdir()) == before
    assert summary["crack_spread_proxy_status"] == "RESEARCH_ONLY"


def test_no_forward_fill_in_crack_spread_trend() -> None:
    crack_df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-06-10", "2026-06-11", "2026-06-12"]),
            "gasoline_crack_research_proxy": [18.0, 20.0, float("nan")],
            "distillate_crack_research_proxy": [24.0, 23.0, float("nan")],
            "crack_321_research_proxy": [20.0, 20.0, float("nan")],
        }
    )

    trends = classify_crack_spread_proxy_trend(crack_df)

    assert trends["gasoline_crack_research_proxy_trend"] == "UP"
    assert trends["distillate_crack_research_proxy_trend"] == "DOWN"
    assert trends["crack_321_research_proxy_trend"] == "FLAT"
