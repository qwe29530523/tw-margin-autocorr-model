from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from src.common.io import ensure_dir


def write_oil_crack_spread_chart(frame: pd.DataFrame, output_path: Path, mock_data_only: bool = False) -> Path:
    ensure_dir(output_path.parent)
    df = frame.sort_values("date").copy()
    gasoline = pd.to_numeric(df.get("gasoline_crack_proxy"), errors="coerce")
    diesel = pd.to_numeric(df.get("diesel_crack_proxy"), errors="coerce")
    fig, ax = plt.subplots(figsize=(11, 5.5))
    if gasoline.notna().any():
        ax.plot(df["date"], gasoline, label="Gasoline crack proxy", linewidth=1.0)
        ax.plot(df["date"], gasoline.diff(20), label="Gasoline 20D change", linewidth=0.9)
    if diesel.notna().any():
        ax.plot(df["date"], diesel, label="Diesel crack proxy", linewidth=1.0)
        ax.plot(df["date"], diesel.diff(20), label="Diesel 20D change", linewidth=0.9)
    if not gasoline.notna().any() and not diesel.notna().any():
        ax.text(0.5, 0.5, "Crack spread proxy missing", transform=ax.transAxes, ha="center", va="center")
    ax.axhline(0, color="#555555", linewidth=0.8)
    ax.set_title(("[MOCK DATA ONLY] " if mock_data_only else "") + "Oil Crack Spread Proxy")
    if ax.get_legend_handles_labels()[0]:
        ax.legend(loc="upper left")
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path
