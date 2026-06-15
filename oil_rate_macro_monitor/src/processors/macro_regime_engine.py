from __future__ import annotations

from typing import Any

import pandas as pd

PRODUCT_DEMAND_WEAK_SIGNALS = {
    "demand_weakening",
    "broad_product_demand_softening",
    "product_demand_softening_with_elevated_cracks",
}


def build_macro_summary(
    oil_frame: pd.DataFrame,
    rates_frame: pd.DataFrame,
    yahoo_overlay: bool = False,
) -> dict[str, Any]:
    oil = _latest(oil_frame)
    rates = _latest(rates_frame)
    macro_regime = _macro_regime(oil, rates)
    secondary_regime = _secondary_regime(oil, rates, macro_regime)
    reasons = _reasons(oil, rates, macro_regime, secondary_regime)
    warnings = _warnings(oil, rates, yahoo_overlay)
    data_completeness_score = _data_completeness_score(oil, rates)
    regime_confidence_score = _regime_confidence_score(oil, rates, reasons, warnings, data_completeness_score)
    return {
        "macro_regime": macro_regime,
        "regime": macro_regime,
        "secondary_regime": secondary_regime,
        "data_completeness_score": data_completeness_score,
        "regime_confidence_score": regime_confidence_score,
        "confidence_score": regime_confidence_score,
        "reasons": reasons,
        "warnings": warnings,
        "metrics": _metrics(oil, rates, yahoo_overlay),
    }


def _macro_regime(oil: dict[str, Any], rates: dict[str, Any]) -> str:
    oil_momentum = oil.get("oil_momentum_signal")
    inventory = oil.get("inventory_signal")
    product = oil.get("product_demand_signal")
    rates_regime = rates.get("rates_regime")
    funding = rates.get("funding_pressure_signal")
    carry = rates.get("carry_signal")
    if (
        oil_momentum == "oil_up_medium_term"
        and inventory == "inventory_tightening"
        and product in {"product_demand_gasoline_led", "product_demand_diesel_led"}
        and rates_regime in {"bear_steepening", "policy_tight"}
    ):
        return "inflation_pressure"
    if (
        oil_momentum in {"oil_up_medium_term", "oil_up_short_term"}
        and product in {"product_demand_gasoline_led", "product_demand_diesel_led"}
        and inventory != "inventory_building"
        and funding not in {"funding_pressure_elevated", "funding_pressure_stress"}
        and carry != "negative_carry"
    ):
        return "growth_strength"
    if (
        inventory == "inventory_tightening"
        and product in PRODUCT_DEMAND_WEAK_SIGNALS
        and rates_regime in {"negative_carry", "inversion_pressure", "policy_tight", "mixed"}
    ):
        return "neutral_mixed"
    if (
        oil_momentum == "oil_down_medium_term"
        and inventory == "inventory_building"
        and product in PRODUCT_DEMAND_WEAK_SIGNALS
        and rates_regime in {"bull_steepening", "inversion_pressure", "mixed"}
    ):
        return "recession_pressure"
    if oil.get("wti_return_5d", 0) > 0.05 and inventory == "inventory_tightening":
        return "supply_shock"
    return "neutral_mixed"


def _secondary_regime(oil: dict[str, Any], rates: dict[str, Any], macro_regime: str) -> str:
    if oil.get("inventory_signal") == "inventory_tightening" and oil.get("product_demand_signal") in PRODUCT_DEMAND_WEAK_SIGNALS:
        return "tight_inventory_weak_products"
    if oil.get("oil_momentum_signal") in {"oil_up_medium_term", "oil_up_short_term"} and rates.get("carry_signal") == "negative_carry":
        return "cost_pressure_with_financial_drag"
    if oil.get("oil_momentum_signal") == "oil_down_medium_term" and rates.get("carry_signal") == "carry_repair":
        return "disinflation_with_bond_support"
    return "none" if macro_regime != "neutral_mixed" else "mixed"


def _reasons(
    oil: dict[str, Any],
    rates: dict[str, Any],
    macro_regime: str,
    secondary_regime: str,
) -> list[str]:
    reasons = [
        f"Oil regime: {oil.get('oil_regime', 'missing')}",
        f"Inventory signal: {oil.get('inventory_signal', 'missing')}",
        f"Product demand signal: {oil.get('product_demand_signal', 'missing')}",
        f"Rates regime: {rates.get('rates_regime', 'missing')}",
    ]
    if secondary_regime == "tight_inventory_weak_products":
        reasons.append("庫存偏緊，但產品端需求動能轉弱，屬於供需混合訊號。")
    if macro_regime == "neutral_mixed":
        reasons.append("沒有單一 macro regime 明確成立。")
    return reasons


def _warnings(oil: dict[str, Any], rates: dict[str, Any], yahoo_overlay: bool) -> list[str]:
    warnings: list[str] = []
    if not yahoo_overlay:
        warnings.append("Yahoo overlay OFF")
    if oil.get("curve_state", "unknown") == "unknown":
        warnings.append("Futures curve is unavailable in core FRED+EIA mode.")
    warnings.append("Premium/manual data required for futures curve, OSP, freight, DUC, and global upstream CAPEX.")
    for label, value in {
        "WTI": oil.get("wti"),
        "Brent": oil.get("brent"),
        "10Y": rates.get("ten_year"),
        "2Y": rates.get("two_year"),
        "SOFR": rates.get("sofr"),
    }.items():
        if _missing(value):
            warnings.append(f"{label} data missing.")
    return warnings


def _data_completeness_score(oil: dict[str, Any], rates: dict[str, Any]) -> int:
    required_fields = {
        "WTI": oil.get("wti"),
        "Brent": oil.get("brent"),
        "crude_inventory": oil.get("crude_inventory"),
        "gasoline_inventory": oil.get("gasoline_inventory"),
        "distillate_inventory": oil.get("distillate_inventory"),
        "gasoline_product_supplied": oil.get("gasoline_product_supplied"),
        "distillate_product_supplied": oil.get("distillate_product_supplied"),
        "jet_fuel_product_supplied": oil.get("jet_fuel_product_supplied"),
        "Fed Funds": rates.get("fedfunds"),
        "SOFR": rates.get("sofr"),
        "3M": rates.get("three_month"),
        "2Y": rates.get("two_year"),
        "5Y": rates.get("five_year"),
        "10Y": rates.get("ten_year"),
        "30Y": rates.get("thirty_year"),
    }
    present = sum(not _missing(value) for value in required_fields.values())
    return int(round(present / len(required_fields) * 100))


def _regime_confidence_score(
    oil: dict[str, Any],
    rates: dict[str, Any],
    reasons: list[str],
    warnings: list[str],
    data_completeness_score: int,
) -> int:
    score = 35 + min(25, len(reasons) * 4)
    if oil.get("inventory_signal") != "mixed":
        score += 8
    if oil.get("product_demand_signal") not in {None, "mixed_product_demand"}:
        score += 8
    if rates.get("rates_regime") not in {None, "mixed", "belly_normal"}:
        score += 8
    if data_completeness_score >= 90:
        score += 5
    elif data_completeness_score < 70:
        score -= 10
    for warning in warnings:
        normalized = warning.lower()
        if "missing" in normalized:
            score -= 10
        if "futures curve" in normalized or "premium/manual" in normalized:
            score -= 10
    return int(max(0, min(100, score)))


def _metrics(oil: dict[str, Any], rates: dict[str, Any], yahoo_overlay: bool) -> dict[str, Any]:
    metrics = {}
    metrics.update(oil)
    metrics.update(rates)
    metrics["data_source_mode"] = "Core FRED + EIA"
    metrics["yahoo_overlay"] = "ON" if yahoo_overlay else "OFF"
    return metrics


def _latest(df: pd.DataFrame) -> dict[str, Any]:
    if df is None or df.empty:
        return {}
    return df.dropna(how="all").iloc[-1].to_dict()


def _missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except Exception:  # noqa: BLE001
        return False
