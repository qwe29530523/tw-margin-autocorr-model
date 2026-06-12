from __future__ import annotations


def clamp_score(value: float) -> int:
    return int(max(0, min(100, round(value))))


def risk_level_from_signal(final_signal: str, market_extreme_warning: bool = False) -> str:
    if final_signal == "DELEVERAGING_RISK":
        return "high"
    if final_signal == "LATE_CYCLE_LEVERAGE_WARNING":
        return "high"
    if final_signal in {"HOT_LEVERAGE_MOMENTUM", "DISTRIBUTION_WARNING"}:
        return "medium"
    return "low"
