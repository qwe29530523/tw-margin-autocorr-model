from __future__ import annotations

import pandas as pd

from src.systems.oil_market.processors.inventory_engine import _change_4w


def build_refinery_metrics(frame: pd.DataFrame) -> dict:
    df = frame.sort_values("date").copy()
    utilization = None
    inputs = None
    if not df.empty:
        utilization = float(pd.to_numeric(df["refinery_utilization"], errors="coerce").dropna().iloc[-1])
        inputs = float(pd.to_numeric(df["refinery_crude_inputs"], errors="coerce").dropna().iloc[-1])
    utilization_change = _change_4w(df, "refinery_utilization")
    inputs_change = _change_4w(df, "refinery_crude_inputs")
    if utilization is not None and utilization >= 92 and inputs_change is not None and inputs_change > 0:
        signal = "refinery_running_hot"
    elif utilization_change is not None and inputs_change is not None and utilization_change < 0 and inputs_change < 0:
        signal = "refinery_slowing"
    elif utilization_change is not None and utilization_change < 0:
        signal = "maintenance_distortion"
    else:
        signal = "neutral"
    return {
        "refinery_utilization": utilization,
        "refinery_crude_inputs": inputs,
        "refinery_utilization_4w_change": utilization_change,
        "refinery_crude_inputs_4w_change": inputs_change,
        "refinery_signal": signal,
    }
