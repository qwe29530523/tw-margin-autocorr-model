from __future__ import annotations

from src.common.dates import today_taipei


DEFAULT_ALLOCATION_VIEW = {
    "equity": "neutral",
    "high_beta": "neutral",
    "bonds": "neutral",
    "cash": "neutral",
    "commodities": "neutral",
    "defensive_assets": "neutral",
}

SUMMARY_KEYS = [
    "system",
    "report_date",
    "tw_margin_system_ready",
    "oil_market_system_ready",
    "rates_cpi_system_ready",
    "tw_margin_final_signal",
    "tw_leverage_cycle_phase",
    "tw_risk_level",
    "oil_regime",
    "oil_momentum_signal",
    "inventory_signal",
    "product_demand_signal",
    "supply_signal",
    "price_war_risk",
    "supply_shock_risk",
    "demand_destruction_risk",
    "rates_regime",
    "funding_pressure_signal",
    "carry_signal",
    "curve_signal",
    "cpi_nowcast_signal",
    "equity_risk_score",
    "bond_support_score",
    "inflation_risk_score",
    "deleveraging_risk_score",
    "commodity_pressure_score",
    "macro_tightening_score",
    "final_market_state",
    "asset_allocation_view",
    "integration_reasons",
    "warnings",
]


def _ready(summary: dict, expected_system: str) -> bool:
    if summary.get("system") != expected_system:
        return False
    if summary.get("mock_mode") is True:
        return False
    if "real_data_ready" in summary and summary.get("real_data_ready") is not True:
        return False
    if "data_validation_passed" in summary and summary.get("data_validation_passed") is not True:
        return False
    return True


def _value(summary: dict, *keys, default=None):
    for key in keys:
        if summary.get(key) is not None:
            return summary.get(key)
    return default


def _is_rates_supportive(rates_regime: str | None, carry: str | None, funding: str | None, cpi: str | None) -> bool:
    return (
        rates_regime in {"neutral", "carry_repair"}
        or carry in {"carry_positive", "carry_repair"}
        or funding == "funding_pressure_low"
    ) and cpi != "inflationary"


def _is_rates_pressure(rates_regime: str | None, funding: str | None, curve: str | None) -> bool:
    return (
        rates_regime == "macro_tightening"
        or funding in {"funding_pressure_elevated", "funding_pressure_stress"}
        or curve in {"partial_inversion", "deep_inversion"}
    )


def _is_oil_inflationary(oil_regime: str | None) -> bool:
    return oil_regime in {"supply_led_tightness", "supply_shock", "demand_led_strength"}


def _is_rates_support_absent(rates_regime: str | None, carry: str | None, funding: str | None) -> bool:
    return rates_regime == "macro_tightening" or carry == "carry_negative" or funding in {
        "funding_pressure_elevated",
        "funding_pressure_stress",
    }


def _score(*conditions: tuple[bool, int], floor: int = 0) -> int:
    return min(100, max(floor, sum(points for applies, points in conditions if applies)))


def _allocation_for_state(state: str) -> dict[str, str]:
    allocation = dict(DEFAULT_ALLOCATION_VIEW)
    if state == "late_cycle_but_bond_supported":
        allocation.update({"equity": "selective", "high_beta": "trim", "bonds": "add_on_dips", "cash": "neutral"})
    elif state == "late_cycle_with_inflation_pressure":
        allocation.update(
            {
                "equity": "reduce",
                "high_beta": "underweight",
                "bonds": "neutral",
                "cash": "raise",
                "commodities": "selective",
                "defensive_assets": "overweight",
            }
        )
    elif state == "overheat_with_rate_pressure":
        allocation.update(
            {
                "equity": "reduce",
                "high_beta": "underweight",
                "bonds": "short_duration",
                "cash": "raise",
                "defensive_assets": "overweight",
            }
        )
    elif state == "deleveraging_pressure":
        allocation.update(
            {
                "equity": "underweight",
                "high_beta": "avoid",
                "bonds": "quality_duration",
                "cash": "high",
                "defensive_assets": "overweight",
            }
        )
    elif state == "stagflation_late_cycle_risk":
        allocation.update(
            {
                "equity": "underweight",
                "high_beta": "avoid",
                "bonds": "short_duration",
                "cash": "high",
                "commodities": "selective_overweight",
                "defensive_assets": "overweight",
            }
        )
    elif state == "growth_risk_on":
        allocation.update(
            {
                "equity": "overweight",
                "high_beta": "selective_overweight",
                "bonds": "underweight",
                "cash": "low",
            }
        )
    return allocation


def integrate_regimes(tw: dict, oil: dict, rates_cpi: dict | None = None) -> dict:
    rates_cpi = rates_cpi or {}
    tw_signal = _value(tw, "final_signal")
    tw_phase = _value(tw, "leverage_cycle_phase")
    tw_risk_level = _value(tw, "risk_level")
    oil_regime = _value(oil, "oil_regime")
    oil_momentum = _value(oil, "oil_momentum_signal")
    inventory = _value(oil, "inventory_signal")
    product_demand = _value(oil, "product_demand_signal")
    supply = _value(oil, "supply_signal")
    rates_regime = _value(rates_cpi, "rates_regime")
    funding = _value(rates_cpi, "funding_pressure_signal")
    carry = _value(rates_cpi, "carry_signal")
    curve = _value(rates_cpi, "curve_signal")
    cpi = _value(rates_cpi, "cpi_nowcast_signal")
    margin_signal = str(_value(tw, "margin_cycle_signal", "transition_watch", default="")).lower()

    tw_ready = _ready(tw, "tw_margin_cycle")
    oil_ready = _ready(oil, "oil_market")
    rates_ready = _ready(rates_cpi, "rates_cpi")
    late_cycle = tw_signal == "LATE_CYCLE_LEVERAGE_WARNING"
    deleveraging = tw_signal == "DELEVERAGING_RISK" or (
        tw_risk_level == "high" and any(token in margin_signal for token in ["weakening", "deleveraging", "down"])
    )
    rates_supportive = _is_rates_supportive(rates_regime, carry, funding, cpi)
    rates_pressure = _is_rates_pressure(rates_regime, funding, curve)
    oil_inflationary = _is_oil_inflationary(oil_regime)
    oil_supply_pressure = oil_regime in {"supply_led_tightness", "supply_shock"}

    if deleveraging:
        state = "deleveraging_pressure"
    elif late_cycle and oil_supply_pressure and cpi == "inflationary" and _is_rates_support_absent(rates_regime, carry, funding):
        state = "stagflation_late_cycle_risk"
    elif late_cycle and rates_pressure and cpi == "inflationary":
        state = "overheat_with_rate_pressure"
    elif late_cycle and cpi == "inflationary" and oil_inflationary:
        state = "late_cycle_with_inflation_pressure"
    elif late_cycle and rates_supportive and oil_regime not in {"supply_shock", "demand_led_strength"}:
        state = "late_cycle_but_bond_supported"
    elif tw_signal in {"NORMAL", "HOT_LEVERAGE_MOMENTUM"} or tw_phase in {"normal", "hot_leverage_momentum"}:
        state = "growth_risk_on" if not oil_inflationary and (rates_supportive or rates_regime == "neutral") else "neutral_mixed"
    else:
        state = "neutral_mixed"

    equity_risk = _score(
        (late_cycle, 25),
        (deleveraging, 40),
        (oil_regime in {"supply_shock", "supply_led_tightness"}, 20),
        (rates_pressure, 20),
        (cpi == "inflationary", 15),
        floor=20,
    )
    bond_support = _score(
        (rates_regime == "carry_repair", 30),
        (carry in {"carry_positive", "carry_repair"}, 20),
        (cpi == "disinflationary", 30),
        (funding == "funding_pressure_low", 20),
        (rates_pressure, -20),
        floor=10,
    )
    inflation_risk = _score(
        (cpi == "inflationary", 40),
        (oil_regime in {"supply_led_tightness", "supply_shock"}, 25),
        (oil_regime == "demand_led_strength", 30),
        (oil_momentum in {"bullish", "uptrend", "strong_uptrend"}, 10),
        (product_demand in {"strong", "demand_strength"}, 10),
        floor=15,
    )
    deleveraging_risk = _score(
        (deleveraging, 85),
        (tw_risk_level == "high", 20),
        ("weakening" in margin_signal, 35),
        floor=10,
    )
    commodity_pressure = _score(
        (oil_regime == "supply_shock", 45),
        (oil_regime == "supply_led_tightness", 70),
        (oil_momentum in {"bullish", "uptrend", "strong_uptrend"}, 20),
        (inventory in {"tightening", "drawdown", "inventory_draw"}, 20),
        (supply in {"supply_shock", "tight"}, 20),
        floor=10,
    )
    macro_tightening = _score(
        (rates_regime == "macro_tightening", 40),
        (funding in {"funding_pressure_elevated", "funding_pressure_stress"}, 25),
        (curve in {"partial_inversion", "deep_inversion"}, 20),
        (cpi == "inflationary", 15),
        floor=10,
    )

    warnings = []
    if not tw_ready:
        warnings.append("System A tw_margin_cycle is not ready; integration confidence lowered.")
    if not oil_ready:
        warnings.append("System B oil_market is not real-data ready; integration confidence lowered.")
    if not rates_ready:
        warnings.append("System C rates_cpi is not real-data ready; integration confidence lowered.")

    reasons = [
        f"TW signal={tw_signal or 'missing'}, phase={tw_phase or 'missing'}, risk={tw_risk_level or 'missing'}.",
        f"Oil regime={oil_regime or 'missing'}, momentum={oil_momentum or 'missing'}, inventory={inventory or 'missing'}.",
        f"Rates regime={rates_regime or 'missing'}, funding={funding or 'missing'}, carry={carry or 'missing'}, CPI={cpi or 'missing'}.",
        f"Selected final_market_state={state}.",
    ]

    summary = {
        "system": "macro_integration",
        "report_date": today_taipei().isoformat(),
        "tw_margin_system_ready": tw_ready,
        "oil_market_system_ready": oil_ready,
        "rates_cpi_system_ready": rates_ready,
        "tw_margin_final_signal": tw_signal,
        "tw_leverage_cycle_phase": tw_phase,
        "tw_risk_level": tw_risk_level,
        "oil_regime": oil_regime,
        "oil_momentum_signal": oil_momentum,
        "inventory_signal": inventory,
        "product_demand_signal": product_demand,
        "supply_signal": supply,
        "price_war_risk": _value(oil, "price_war_risk"),
        "supply_shock_risk": _value(oil, "supply_shock_risk"),
        "demand_destruction_risk": _value(oil, "demand_destruction_risk"),
        "rates_regime": rates_regime,
        "funding_pressure_signal": funding,
        "carry_signal": carry,
        "curve_signal": curve,
        "cpi_nowcast_signal": cpi,
        "equity_risk_score": equity_risk,
        "bond_support_score": bond_support,
        "inflation_risk_score": inflation_risk,
        "deleveraging_risk_score": deleveraging_risk,
        "commodity_pressure_score": commodity_pressure,
        "macro_tightening_score": macro_tightening,
        "final_market_state": state,
        "asset_allocation_view": _allocation_for_state(state),
        "integration_reasons": reasons,
        "warnings": warnings,
    }
    return {key: summary.get(key) for key in SUMMARY_KEYS}
