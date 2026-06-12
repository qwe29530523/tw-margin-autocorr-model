from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from src.common.io import ensure_dir


def write_oil_product_demand_chart(frame: pd.DataFrame, output_path: Path, mock_data_only: bool = False) -> Path:
    ensure_dir(output_path.parent)
    df = frame.sort_values("date").copy()
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for column, label in [
        ("gasoline_product_supplied", "Gasoline supplied"),
        ("distillate_product_supplied", "Distillate supplied"),
        ("jet_fuel_product_supplied", "Jet fuel supplied"),
    ]:
        ax.plot(df["date"], pd.to_numeric(df[column], errors="coerce").diff(4), label=label, linewidth=1.0)
    ax.axhline(0, color="#555555", linewidth=0.8)
    ax.set_title(("[MOCK DATA ONLY] " if mock_data_only else "") + "Oil Product Demand 4W Change")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path
