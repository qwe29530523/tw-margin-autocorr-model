from __future__ import annotations

from typing import Any

from src.common.scoring import risk_level_from_signal


def _num(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def classify_tw_margin_cycle(row: dict[str, Any]) -> dict[str, Any]:
    raw_signal = str(row.get("raw_signal") or row.get("signal") or "NORMAL")
    market_extreme = bool(row.get("market_extreme_warning", False))
    index_extreme = _num(row, "index_yoy_z") > 2 or _num(row, "index_qoq_z") > 2
    margin_extreme = _num(row, "margin_roc_z") > 2 and _num(row, "margin_roc") > 0.40
    high_persistence = _num(row, "margin_roc_persistence_score") > 0.70
    distribution = _num(row, "index_qoq_change_20d") < 0 and _num(row, "margin_roc") > 0.40
    deleveraging = (
        (_num(row, "index_close_return_20d") < 0 or _num(row, "index_close_return_60d") < 0)
        and _num(row, "margin_roc_change_20d") < 0
        and _num(row, "margin_balance_change_20d") < 0
        and market_extreme
    )

    reasons: list[str] = []
    if deleveraging:
        final_signal = "DELEVERAGING_RISK"
        phase = "deleveraging_risk"
        reasons.append("index_return_weak_and_margin_balance_declining_after_extreme")
    elif index_extreme and margin_extreme and high_persistence:
        final_signal = "LATE_CYCLE_LEVERAGE_WARNING"
        phase = "late_cycle_leverage_warning"
        reasons.append("index_and_margin_extreme_with_high_persistence")
    elif distribution:
        final_signal = "DISTRIBUTION_WARNING"
        phase = "late_cycle_leverage_warning"
        reasons.append("index_qoq_turning_weaker_while_margin_roc_remains_high")
    elif index_extreme and margin_extreme:
        final_signal = "HOT_LEVERAGE_MOMENTUM"
        phase = "hot_leverage_momentum"
        reasons.append("index_growth_and_margin_expansion_extreme")
    else:
        final_signal = raw_signal
        phase = {
            "HOT_LEVERAGE_MOMENTUM": "hot_leverage_momentum",
            "LATE_CYCLE_LEVERAGE_WARNING": "late_cycle_leverage_warning",
            "DELEVERAGING_RISK": "deleveraging_risk",
        }.get(final_signal, "normal")
        reasons.append(f"raw_signal={raw_signal}")

    return {
        "raw_signal": raw_signal,
        "final_signal": final_signal,
        "leverage_cycle_phase": phase,
        "risk_level": risk_level_from_signal(final_signal, market_extreme),
        "final_signal_reasons": reasons,
        "transition_watch": "distribution_warning" if distribution and not deleveraging else "none",
    }
