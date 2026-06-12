from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from src.common.io import ensure_dir


def _title(text: str, mock_data_only: bool) -> str:
    return f"[MOCK DATA ONLY] {text}" if mock_data_only else text


def write_oil_price_chart(frame: pd.DataFrame, output_path: Path, mock_data_only: bool = False) -> Path:
    ensure_dir(output_path.parent)
    df = frame.sort_values("date").copy()
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    axes[0].plot(df["date"], df["wti"], label="WTI", color="#4c78a8", linewidth=1.1)
    axes[0].plot(df["date"], df["brent"], label="Brent", color="#f58518", linewidth=1.1)
    axes[0].set_title(_title("Oil Price Momentum", mock_data_only))
    axes[0].legend(loc="upper left")
    axes[0].grid(True, alpha=0.2)
    wti = pd.to_numeric(df["wti"], errors="coerce")
    axes[1].plot(df["date"], wti.pct_change(5), label="WTI 5D", linewidth=0.9)
    axes[1].plot(df["date"], wti.pct_change(20), label="WTI 20D", linewidth=0.9)
    axes[1].plot(df["date"], wti.pct_change(60), label="WTI 60D", linewidth=0.9)
    axes[1].axhline(0, color="#555555", linewidth=0.8)
    axes[1].legend(loc="upper left")
    axes[1].grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path
