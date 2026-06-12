from __future__ import annotations

import pandas as pd


def _change_4w(df: pd.DataFrame, column: str) -> float | None:
    if column not in df or len(df) < 2:
        return None
    series = pd.to_numeric(df[column], errors="coerce").dropna()
    if len(series) < 2:
        return None
    lookback = min(4, len(series) - 1)
    return float(series.iloc[-1] - series.iloc[-lookback - 1])


def inventory_signal(crude: float | None, gasoline: float | None, distillate: float | None, total: float | None) -> str:
    crude = 0.0 if crude is None else crude
    gasoline = 0.0 if gasoline is None else gasoline
    distillate = 0.0 if distillate is None else distillate
    if crude < 0 and (gasoline > 0 or distillate > 0):
        return "crude_tight_product_loose"
    if crude > 0 and (gasoline < 0 or distillate < 0):
        return "product_tight_crude_loose"
    if total is not None and total < 0:
        return "inventory_tightening"
    if total is not None and total > 0:
        return "inventory_building"
    return "neutral"


def build_inventory_metrics(frame: pd.DataFrame) -> dict:
    df = frame.sort_values("date").copy()
    crude = _change_4w(df, "crude_inventory")
    gasoline = _change_4w(df, "gasoline_inventory")
    distillate = _change_4w(df, "distillate_inventory")
    total = None if any(value is None for value in [crude, gasoline, distillate]) else crude + gasoline + distillate
    latest_date = None if df.empty else pd.to_datetime(df["date"].iloc[-1]).date().isoformat()
    return {
        "inventory_asof_date": latest_date,
        "crude_inventory_4w_change": crude,
        "gasoline_inventory_4w_change": gasoline,
        "distillate_inventory_4w_change": distillate,
        "total_inventory_proxy_4w_change": total,
        "inventory_signal": inventory_signal(crude, gasoline, distillate, total),
    }
