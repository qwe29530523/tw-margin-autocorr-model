from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from src.common.io import ensure_dir


def _title(text: str, mock_data_only: bool) -> str:
    return f"[MOCK DATA ONLY] {text}" if mock_data_only else text


def _pivot_rates(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    df = frame.copy()
    df["date"] = pd.to_datetime(df["date"])
    return df.pivot_table(index="date", columns="series", values="value", aggfunc="last").sort_index()


def write_rates_curve_chart(frame: pd.DataFrame, output_path: Path, mock_data_only: bool = False) -> Path:
    ensure_dir(output_path.parent)
    pivot = _pivot_rates(frame)
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for series in ["DGS3MO", "DGS1", "DGS2", "DGS5", "DGS10", "DGS30"]:
        if series in pivot:
            ax.plot(pivot.index, pivot[series], label=series, linewidth=1.0)
    if pivot.empty:
        ax.text(0.5, 0.5, "Rates data missing", transform=ax.transAxes, ha="center", va="center")
    ax.set_title(_title("Rates Curve", mock_data_only))
    if ax.get_legend_handles_labels()[0]:
        ax.legend(loc="upper left")
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def write_cpi_nowcast_chart(summary: dict, output_path: Path, mock_data_only: bool = False) -> Path:
    ensure_dir(output_path.parent)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    labels = ["Headline MoM", "Core MoM", "Headline YoY", "Core YoY"]
    values = [
        summary.get("headline_cpi_mom_nowcast") or 0,
        summary.get("core_cpi_mom_nowcast") or 0,
        summary.get("headline_cpi_yoy_nowcast") or 0,
        summary.get("core_cpi_yoy_nowcast") or 0,
    ]
    ax.bar(labels, values, color=["#4c78a8", "#72b7b2", "#f58518", "#e45756"])
    ax.axhline(0, color="#555555", linewidth=0.8)
    ax.set_title(_title("CPI Nowcast", mock_data_only))
    ax.grid(True, axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def write_cpi_component_trend_chart(components: dict, output_path: Path, mock_data_only: bool = False) -> Path:
    ensure_dir(output_path.parent)
    trends = components.get("component_trends", {})
    labels = {
        "energy_proxy_mom": "Energy CPI",
        "food_proxy_mom": "Food CPI",
        "shelter_proxy_mom": "Shelter CPI",
        "core_goods_proxy_mom": "Core Goods",
        "core_services_ex_shelter_proxy_mom": "Core Services ex Shelter",
    }
    fig, ax = plt.subplots(figsize=(11, 5.5))
    plotted = False
    for key, label in labels.items():
        rows = trends.get(key, [])
        if not rows:
            continue
        df = pd.DataFrame(rows)
        df["month"] = pd.to_datetime(df["month"], format="%Y-%m")
        ax.plot(df["month"], df["mom"] * 100, label=label, linewidth=1.0)
        plotted = True
    if not plotted:
        ax.text(0.5, 0.5, "CPI component trend data missing", transform=ax.transAxes, ha="center", va="center")
    ax.axhline(0, color="#555555", linewidth=0.8)
    ax.set_title(_title("CPI Component Trends", mock_data_only))
    ax.set_ylabel("MoM %")
    if ax.get_legend_handles_labels()[0]:
        ax.legend(loc="upper left")
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def write_rates_cpi_dashboard_chart(
    rates_frame: pd.DataFrame,
    summary: dict,
    output_path: Path,
    mock_data_only: bool = False,
) -> Path:
    ensure_dir(output_path.parent)
    pivot = _pivot_rates(rates_frame)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle(_title("Rates × CPI Dashboard", mock_data_only), fontsize=12, fontweight="bold")
    if not pivot.empty:
        for series in ["DGS2", "DGS10", "DGS30"]:
            if series in pivot:
                axes[0].plot(pivot.index, pivot[series], label=series)
    else:
        axes[0].text(0.5, 0.5, "Rates data missing", transform=axes[0].transAxes, ha="center", va="center")
    axes[0].set_title(_title("Selected Rates", mock_data_only))
    if axes[0].get_legend_handles_labels()[0]:
        axes[0].legend(loc="upper left")
    labels = ["Headline MoM", "Core MoM"]
    values = [summary.get("headline_cpi_mom_nowcast") or 0, summary.get("core_cpi_mom_nowcast") or 0]
    axes[1].bar(labels, values, color=["#4c78a8", "#72b7b2"])
    axes[1].set_title(_title("CPI Nowcast", mock_data_only))
    for ax in axes:
        ax.grid(True, alpha=0.2)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path
