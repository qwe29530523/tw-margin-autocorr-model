from __future__ import annotations

from src.systems.macro_integration.regime_matrix import DEFAULT_ALLOCATION_VIEW


def asset_allocation_view(state: str) -> dict[str, str]:
    allocation = dict(DEFAULT_ALLOCATION_VIEW)
    if state == "overheat_with_rate_pressure":
        allocation.update({"equity": "reduce", "high_beta": "underweight", "bonds": "short_duration", "cash": "raise", "defensive_assets": "overweight"})
    elif state == "late_cycle_but_bond_supported":
        allocation.update({"equity": "selective", "high_beta": "trim", "bonds": "add_on_dips", "cash": "neutral"})
    elif state == "late_cycle_with_inflation_pressure":
        allocation.update({"equity": "reduce", "high_beta": "underweight", "cash": "raise", "commodities": "selective", "defensive_assets": "overweight"})
    elif state == "stagflation_late_cycle_risk":
        allocation.update({"equity": "underweight", "high_beta": "avoid", "bonds": "short_duration", "cash": "high", "commodities": "selective_overweight", "defensive_assets": "overweight"})
    elif state == "deleveraging_pressure":
        allocation.update({"equity": "underweight", "high_beta": "avoid", "bonds": "quality_duration", "cash": "high", "defensive_assets": "overweight"})
    elif state == "growth_risk_on":
        allocation.update({"equity": "overweight", "high_beta": "selective_overweight", "bonds": "underweight", "cash": "low"})
    return allocation
