from __future__ import annotations

from typing import Any

import pandas as pd


MODULE_NAME = "oil_macro_core"
WTI_CURVE_BLOCKED = "BLOCKED_VENDOR_NOT_CONFIGURED"
MISSING = "MISSING"
RESEARCH_ONLY = "RESEARCH_ONLY"

CRACK_TREND_COLUMNS = {
    "gasoline_crack_research_proxy": "gasoline_crack_research_proxy_trend",
    "distillate_crack_research_proxy": "distillate_crack_research_proxy_trend",
    "crack_321_research_proxy": "crack_321_research_proxy_trend",
}

FORBIDDEN_OUTPUTS = {
    "production_score",
    "composite_score",
    "final_trading_signal",
    "buy_signal",
    "sell_signal",
}


def build_oil_macro_summary(
    oil_rate_df: pd.DataFrame | None = None,
    physical_df: pd.DataFrame | None = None,
    crack_spread_research_df: pd.DataFrame | None = None,
    positioning_df: pd.DataFrame | None = None,
    coverage_df: pd.DataFrame | None = None,
    as_of_date: object | None = None,
) -> dict[str, Any]:
    crack_trends = classify_crack_spread_proxy_trend(crack_spread_research_df)
    crack_spread_proxy_status = _crack_spread_proxy_status(crack_spread_research_df)

    summary_fields: dict[str, Any] = {
        "module_name": MODULE_NAME,
        "as_of_date": _summary_as_of_date(
            as_of_date,
            [oil_rate_df, physical_df, crack_spread_research_df, positioning_df, coverage_df],
        ),
        "oil_rate_mix": _latest_non_null_value(oil_rate_df, "oil_rate_mix"),
        "oil_physical_tightness": _latest_non_null_value(physical_df, "oil_physical_tightness"),
        "product_inventory_pressure": _latest_non_null_value(physical_df, "product_inventory_pressure"),
        "crack_spread_proxy_status": crack_spread_proxy_status,
        "gasoline_crack_research_proxy_trend": crack_trends["gasoline_crack_research_proxy_trend"],
        "distillate_crack_research_proxy_trend": crack_trends["distillate_crack_research_proxy_trend"],
        "crack_321_research_proxy_trend": crack_trends["crack_321_research_proxy_trend"],
        "oil_positioning_state": _latest_non_null_value(positioning_df, "oil_positioning_state"),
        "oil_squeeze_risk": _latest_non_null_value(positioning_df, "oil_squeeze_risk"),
        "wti_curve_status": WTI_CURVE_BLOCKED,
    }

    primary_regime = derive_oil_macro_regime(
        oil_rate_mix=summary_fields["oil_rate_mix"],
        oil_physical_tightness=summary_fields["oil_physical_tightness"],
        product_inventory_pressure=summary_fields["product_inventory_pressure"],
        crack_spread_proxy_status=summary_fields["crack_spread_proxy_status"],
        gasoline_crack_proxy_trend=summary_fields["gasoline_crack_research_proxy_trend"],
        distillate_crack_proxy_trend=summary_fields["distillate_crack_research_proxy_trend"],
        crack_321_proxy_trend=summary_fields["crack_321_research_proxy_trend"],
        oil_positioning_state=summary_fields["oil_positioning_state"],
        oil_squeeze_risk=summary_fields["oil_squeeze_risk"],
        wti_curve_status=summary_fields["wti_curve_status"],
    )
    summary_fields["primary_oil_macro_regime"] = primary_regime
    summary_fields["drivers"] = _build_drivers(summary_fields)
    summary_fields["warning_flags"] = build_oil_warning_flags(summary_fields)
    summary_fields["next_watch_items"] = _build_next_watch_items(summary_fields)
    summary_fields["data_caveats"] = build_oil_data_caveats(coverage_df)
    summary_fields["data_status"] = _build_data_status(summary_fields)
    summary_fields["confidence"] = _build_confidence(summary_fields)
    summary_fields["risk_level"] = _build_risk_level(summary_fields)

    for forbidden_key in FORBIDDEN_OUTPUTS:
        summary_fields.pop(forbidden_key, None)
    return summary_fields


def classify_crack_spread_proxy_trend(crack_spread_research_df: pd.DataFrame | None) -> dict[str, str]:
    trends = {}
    for source_column, output_column in CRACK_TREND_COLUMNS.items():
        trends[output_column] = _classify_numeric_trend(crack_spread_research_df, source_column)
    return trends


def derive_oil_macro_regime(
    oil_rate_mix: object | None = None,
    oil_physical_tightness: object | None = None,
    product_inventory_pressure: object | None = None,
    crack_spread_proxy_status: object | None = None,
    gasoline_crack_proxy_trend: object | None = None,
    distillate_crack_proxy_trend: object | None = None,
    crack_321_proxy_trend: object | None = None,
    oil_positioning_state: object | None = None,
    oil_squeeze_risk: object | None = None,
    wti_curve_status: object | None = None,
) -> str:
    if _all_missing(
        [
            oil_rate_mix,
            oil_physical_tightness,
            product_inventory_pressure,
            crack_spread_proxy_status,
            oil_positioning_state,
            oil_squeeze_risk,
        ]
    ):
        return "MISSING_OIL_MACRO_DATA"

    if _is_physical_tight(oil_physical_tightness) and _has_supportive_crack_proxy(
        gasoline_crack_proxy_trend,
        distillate_crack_proxy_trend,
        crack_321_proxy_trend,
    ):
        return "PHYSICAL_TIGHT_WITH_RESEARCH_PROXY_SUPPORT"

    if (
        _is_physical_tight(oil_physical_tightness)
        and _upper(crack_spread_proxy_status) == MISSING
        and _upper(wti_curve_status) == WTI_CURVE_BLOCKED
    ):
        return "PHYSICAL_TIGHT_BUT_CURVE_BLOCKED"

    if _upper(oil_positioning_state) in {"EXTREME_CROWDED_SHORT", "CROWDED_SHORT"} and _upper(oil_squeeze_risk) in {
        "MEDIUM",
        "HIGH",
        "ELEVATED",
    }:
        return "RESEARCH_PROXY_POSITIONING_SQUEEZE_CANDIDATE"

    if _upper(oil_rate_mix) in {"DISINFLATION_SUPPORT", "GROWTH_SCARE"} and not _is_physical_tight(
        oil_physical_tightness
    ):
        return "DISINFLATION_OR_DEMAND_WEAKNESS"

    return "MIXED_OIL_MACRO_REGIME"


def build_oil_data_caveats(coverage_df: pd.DataFrame | None = None) -> list[str]:
    caveats = [
        "WTI M1/M2/M3 futures curve remains BLOCKED_VENDOR_NOT_CONFIGURED.",
        "No verified CME, exchange, or licensed vendor CL M1/M2/M3 curve source is configured.",
    ]

    for frame in [_as_frame(coverage_df)]:
        if frame.empty:
            continue
        for column in ["caveat", "status", "source_type"]:
            if column not in frame.columns:
                continue
            for value in frame[column].dropna().astype(str):
                if value and value not in caveats:
                    caveats.append(value)
    return caveats


def build_oil_warning_flags(summary_fields: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    if _upper(summary_fields.get("wti_curve_status")) == WTI_CURVE_BLOCKED:
        flags.append("WTI_CURVE_BLOCKED_VENDOR_NOT_CONFIGURED")
    if _upper(summary_fields.get("crack_spread_proxy_status")) == RESEARCH_ONLY:
        flags.append("CRACK_SPREAD_RESEARCH_PROXY_ONLY")
    if _upper(summary_fields.get("oil_positioning_state")) not in {MISSING, ""}:
        flags.append("CFTC_POSITIONING_DIAGNOSTICS_ONLY")
    if _upper(summary_fields.get("oil_rate_mix")) == MISSING:
        flags.append("MISSING_OIL_RATE_MIX")
    if _upper(summary_fields.get("oil_physical_tightness")) == MISSING:
        flags.append("MISSING_OIL_PHYSICAL_TIGHTNESS")
    return _dedupe(flags)


def _classify_numeric_trend(frame: pd.DataFrame | None, column: str) -> str:
    data = _as_frame(frame)
    if data.empty or column not in data.columns:
        return MISSING
    if "date" in data.columns:
        data = data.assign(date=pd.to_datetime(data["date"], errors="coerce")).sort_values("date")
    values = pd.to_numeric(data[column], errors="coerce").dropna()
    if len(values) < 2:
        return MISSING
    latest = float(values.iloc[-1])
    prior = float(values.iloc[-2])
    diff = latest - prior
    if abs(diff) <= 1e-9:
        return "FLAT"
    return "UP" if diff > 0 else "DOWN"


def _latest_non_null_value(frame: pd.DataFrame | None, column: str) -> str:
    data = _as_frame(frame)
    if data.empty or column not in data.columns:
        return MISSING
    if "date" in data.columns:
        data = data.assign(date=pd.to_datetime(data["date"], errors="coerce")).sort_values("date")
    values = data[column].dropna()
    if values.empty:
        return MISSING
    return str(values.iloc[-1])


def _summary_as_of_date(as_of_date: object | None, frames: list[pd.DataFrame | None]) -> str | None:
    if as_of_date is not None:
        return _format_date(as_of_date)
    dates: list[pd.Timestamp] = []
    for frame in frames:
        data = _as_frame(frame)
        if data.empty or "date" not in data.columns:
            continue
        parsed = pd.to_datetime(data["date"], errors="coerce").dropna()
        if not parsed.empty:
            dates.append(parsed.max())
    if not dates:
        return None
    return _format_date(max(dates))


def _format_date(value: object) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return str(value)
    return str(parsed.date())


def _crack_spread_proxy_status(frame: pd.DataFrame | None) -> str:
    data = _as_frame(frame)
    if data.empty:
        return MISSING
    source_type = _latest_non_null_value(data, "source_type")
    data_status = _latest_non_null_value(data, "data_status")
    if source_type == "research_only_public_proxy" or _upper(data_status) == RESEARCH_ONLY:
        return RESEARCH_ONLY
    return "AVAILABLE"


def _build_drivers(summary_fields: dict[str, Any]) -> list[str]:
    drivers: list[str] = []
    if _upper(summary_fields.get("oil_rate_mix")) != MISSING:
        drivers.append(f"oil_rate_mix={summary_fields['oil_rate_mix']}")
    if _upper(summary_fields.get("oil_physical_tightness")) != MISSING:
        drivers.append(f"oil_physical_tightness={summary_fields['oil_physical_tightness']}")
    if _upper(summary_fields.get("product_inventory_pressure")) != MISSING:
        drivers.append(f"product_inventory_pressure={summary_fields['product_inventory_pressure']}")
    if _upper(summary_fields.get("crack_spread_proxy_status")) == RESEARCH_ONLY:
        drivers.append("research_only_crack_spread_proxy_available")
    if _upper(summary_fields.get("oil_positioning_state")) != MISSING:
        drivers.append(f"oil_positioning_state={summary_fields['oil_positioning_state']}")
    return drivers


def _build_next_watch_items(summary_fields: dict[str, Any]) -> list[str]:
    watch_items = ["Verify CME/vendor WTI M1/M2/M3 futures curve before enabling curve inputs."]
    if _upper(summary_fields.get("crack_spread_proxy_status")) in {MISSING, RESEARCH_ONLY}:
        watch_items.append("Validate official RBOB, Heating Oil, and WTI futures/vendor crack spread sources.")
    if _upper(summary_fields.get("oil_positioning_state")) != MISSING:
        watch_items.append("Monitor CFTC positioning as diagnostics only, not a final oil signal.")
    return watch_items


def _build_data_status(summary_fields: dict[str, Any]) -> str:
    if summary_fields.get("primary_oil_macro_regime") == "MISSING_OIL_MACRO_DATA":
        return MISSING
    if _upper(summary_fields.get("crack_spread_proxy_status")) == RESEARCH_ONLY:
        return "RESEARCH_PROXY"
    if any(flag.startswith("MISSING_") for flag in summary_fields.get("warning_flags", [])):
        return "PARTIAL"
    if _upper(summary_fields.get("wti_curve_status")) == WTI_CURVE_BLOCKED:
        return "PARTIAL"
    return "COMPLETE"


def _build_confidence(summary_fields: dict[str, Any]) -> str:
    if summary_fields.get("data_status") == MISSING:
        return "LOW"
    if _upper(summary_fields.get("wti_curve_status")) == WTI_CURVE_BLOCKED:
        return "LOW"
    if summary_fields.get("data_status") in {"PARTIAL", "RESEARCH_PROXY"}:
        return "MEDIUM"
    return "HIGH"


def _build_risk_level(summary_fields: dict[str, Any]) -> str:
    regime = summary_fields.get("primary_oil_macro_regime")
    if regime == "MISSING_OIL_MACRO_DATA":
        return "UNKNOWN"
    if regime in {"PHYSICAL_TIGHT_WITH_RESEARCH_PROXY_SUPPORT", "RESEARCH_PROXY_POSITIONING_SQUEEZE_CANDIDATE"}:
        return "HIGH"
    if regime in {"PHYSICAL_TIGHT_BUT_CURVE_BLOCKED", "MIXED_OIL_MACRO_REGIME"}:
        return "MEDIUM"
    return "LOW"


def _has_supportive_crack_proxy(*trends: object) -> bool:
    return any(_upper(trend) == "UP" for trend in trends)


def _is_physical_tight(value: object) -> bool:
    return _upper(value) == "PHYSICAL_TIGHT"


def _all_missing(values: list[object]) -> bool:
    return all(_upper(value) in {MISSING, ""} for value in values)


def _as_frame(frame: pd.DataFrame | None) -> pd.DataFrame:
    if isinstance(frame, pd.DataFrame):
        return frame.copy()
    return pd.DataFrame()


def _upper(value: object) -> str:
    if value is None or pd.isna(value):
        return MISSING
    return str(value).upper()


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
