from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from src.common.io import ensure_dir


def write_oil_dashboard_chart(
    price_frame: pd.DataFrame,
    eia_frame: pd.DataFrame,
    output_path: Path,
    mock_data_only: bool = False,
) -> Path:
    ensure_dir(output_path.parent)
    price = price_frame.sort_values("date").copy()
    eia = eia_frame.sort_values("date").copy()
    gasoline_crack = pd.to_numeric(eia.get("gasoline_crack_proxy"), errors="coerce")
    diesel_crack = pd.to_numeric(eia.get("diesel_crack_proxy"), errors="coerce")
    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    prefix = "[MOCK DATA ONLY] " if mock_data_only else ""
    fig.suptitle(prefix + "Oil Market Dashboard", fontsize=12, fontweight="bold")
    axes[0, 0].plot(price["date"], price["wti"], label="WTI")
    axes[0, 0].plot(price["date"], price["brent"], label="Brent")
    axes[0, 0].set_title(prefix + "Price")
    axes[0, 0].legend()
    axes[0, 1].plot(eia["date"], pd.to_numeric(eia["crude_inventory"], errors="coerce").diff(4), label="Crude inv 4W")
    axes[0, 1].set_title(prefix + "Inventory")
    axes[1, 0].plot(eia["date"], pd.to_numeric(eia["gasoline_product_supplied"], errors="coerce").diff(4), label="Gasoline")
    axes[1, 0].plot(eia["date"], pd.to_numeric(eia["distillate_product_supplied"], errors="coerce").diff(4), label="Distillate")
    axes[1, 0].set_title(prefix + "Product demand")
    axes[1, 0].legend()
    if gasoline_crack.notna().any():
        axes[1, 1].plot(eia["date"], gasoline_crack, label="Gasoline crack")
    if diesel_crack.notna().any():
        axes[1, 1].plot(eia["date"], diesel_crack, label="Diesel crack")
    if not gasoline_crack.notna().any() and not diesel_crack.notna().any():
        axes[1, 1].text(0.5, 0.5, "Crack proxy missing", transform=axes[1, 1].transAxes, ha="center", va="center")
    axes[1, 1].set_title(prefix + "Cracks")
    if axes[1, 1].get_legend_handles_labels()[0]:
        axes[1, 1].legend()
    for ax in axes.ravel():
        ax.grid(True, alpha=0.2)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path
