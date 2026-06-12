from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from src.common.io import ensure_dir
from src.systems.oil_market.processors.inventory_engine import _change_4w


def write_oil_inventory_chart(frame: pd.DataFrame, output_path: Path, mock_data_only: bool = False) -> Path:
    ensure_dir(output_path.parent)
    df = frame.sort_values("date").copy()
    for column in ["crude_inventory", "gasoline_inventory", "distillate_inventory"]:
        df[f"{column}_4w_change"] = pd.to_numeric(df[column], errors="coerce").diff(4)
    df["total_inventory_proxy_4w_change"] = (
        df["crude_inventory_4w_change"] + df["gasoline_inventory_4w_change"] + df["distillate_inventory_4w_change"]
    )
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for column, label in [
        ("crude_inventory_4w_change", "Crude"),
        ("gasoline_inventory_4w_change", "Gasoline"),
        ("distillate_inventory_4w_change", "Distillate"),
        ("total_inventory_proxy_4w_change", "Total proxy"),
    ]:
        ax.plot(df["date"], df[column], label=label, linewidth=1.0)
    ax.axhline(0, color="#555555", linewidth=0.8)
    ax.set_title(("[MOCK DATA ONLY] " if mock_data_only else "") + "Oil Inventory Proxy 4W Change")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path
