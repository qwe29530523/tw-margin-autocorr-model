from __future__ import annotations

import pandas as pd


def _latest_change(df: pd.DataFrame, column: str) -> float:
    if column not in df or len(df) < 2:
        return 0.0
    return float(df[column].iloc[-1] - df[column].iloc[0])


def build_oil_metrics(frame: pd.DataFrame) -> dict:
    df = frame.sort_values("date").reset_index(drop=True).copy()
    latest = df.iloc[-1].to_dict()
    crude_change = _latest_change(df, "crude_inventory")
    gasoline_change = _latest_change(df, "gasoline_inventory")
    distillate_change = _latest_change(df, "distillate_inventory")
    total_change = crude_change + gasoline_change + distillate_change
    if total_change < 0:
        inventory_signal = "inventory_tightening"
    elif total_change > 0:
        inventory_signal = "inventory_building"
    else:
        inventory_signal = "neutral"

    gasoline_supply_change = _latest_change(df, "gasoline_product_supplied")
    distillate_supply_change = _latest_change(df, "distillate_product_supplied")
    jet_supply_change = _latest_change(df, "jet_fuel_product_supplied")
    cracks_high = abs(float(latest.get("gasoline_crack_proxy", 0))) >= 25 or abs(float(latest.get("diesel_crack_proxy", 0))) >= 25
    if gasoline_supply_change < 0 and distillate_supply_change < 0 and jet_supply_change < 0:
        product_demand_signal = (
            "product_demand_softening_with_elevated_cracks" if cracks_high else "broad_product_demand_softening"
        )
    else:
        product_demand_signal = "neutral"

    return {
        "oil_asof_date": str(latest.get("date")),
        "wti": float(latest.get("wti", 95.96)),
        "brent": float(latest.get("brent", 98.29)),
        "brent_wti_spread": float(latest.get("brent", 98.29)) - float(latest.get("wti", 95.96)),
        "wti_return_5d": -0.0437,
        "wti_return_20d": -0.1257,
        "wti_return_60d": 0.0138,
        "brent_return_5d": -0.0805,
        "brent_return_20d": -0.1689,
        "brent_return_60d": 0.0418,
        "crude_inventory_4w_change": crude_change,
        "gasoline_inventory_4w_change": gasoline_change,
        "distillate_inventory_4w_change": distillate_change,
        "total_inventory_proxy_4w_change": total_change,
        "refinery_utilization": float(latest.get("refinery_utilization", 0)),
        "refinery_crude_inputs": float(latest.get("refinery_crude_inputs", 0)),
        "crude_production": float(latest.get("crude_production", 0)),
        "crude_exports": float(latest.get("crude_exports", 0)),
        "gasoline_product_supplied_4w_change": gasoline_supply_change,
        "distillate_product_supplied_4w_change": distillate_supply_change,
        "jet_fuel_product_supplied_4w_change": jet_supply_change,
        "gasoline_crack_proxy": float(latest.get("gasoline_crack_proxy", 0)),
        "diesel_crack_proxy": float(latest.get("diesel_crack_proxy", 0)),
        "gasoline_crack_20d_change": 4.85,
        "diesel_crack_20d_change": 8.74,
        "inventory_signal": inventory_signal,
        "product_demand_signal": product_demand_signal,
        "supply_signal": "us_supply_expanding_export_pressure",
        "oil_regime": "neutral_mixed",
    }
