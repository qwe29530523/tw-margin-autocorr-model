from __future__ import annotations

import pandas as pd

from src.systems.oil_market.processors.inventory_engine import _change_4w


def product_demand_signal(gasoline: float | None, distillate: float | None, jet: float | None) -> str:
    values = [0.0 if value is None else value for value in [gasoline, distillate, jet]]
    gasoline, distillate, jet = values
    if gasoline > 0 and distillate > 0 and jet > 0:
        return "broad_product_demand_strength"
    if gasoline < 0 and distillate < 0 and jet < 0:
        return "broad_product_demand_softening"
    if distillate > 0 and gasoline <= 0:
        return "industrial_logistics_strength"
    if (gasoline > 0 or jet > 0) and distillate <= 0:
        return "travel_consumer_strength"
    return "mixed_product_demand"


def build_product_demand_metrics(frame: pd.DataFrame) -> dict:
    df = frame.sort_values("date").copy()
    gasoline = _change_4w(df, "gasoline_product_supplied")
    distillate = _change_4w(df, "distillate_product_supplied")
    jet = _change_4w(df, "jet_fuel_product_supplied")
    latest_date = None if df.empty else pd.to_datetime(df["date"].iloc[-1]).date().isoformat()
    return {
        "product_demand_asof_date": latest_date,
        "gasoline_product_supplied_4w_change": gasoline,
        "distillate_product_supplied_4w_change": distillate,
        "jet_fuel_product_supplied_4w_change": jet,
        "product_demand_signal": product_demand_signal(gasoline, distillate, jet),
    }
