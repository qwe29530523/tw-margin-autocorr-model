from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

from src.common.io import ensure_dir


CHART_PANEL_COUNT = 3
ORIGINAL_STYLE_CHART_NAME = "margin_index_original_style.png"
ORIGINAL_STYLE_RECENT5Y_CHART_NAME = "margin_index_original_style_recent5y.png"
PERCENT_CYCLE_CHART_NAME = "margin_index_yoy_percent_cycle.png"
RECENT5Y_PERCENT_CYCLE_CHART_NAME = "margin_index_yoy_percent_cycle_recent5y.png"
MAIN_CYCLE_CHART_NAME = "margin_index_yoy_standardized_cycle.png"
RECENT5Y_CYCLE_CHART_NAME = "margin_index_yoy_standardized_cycle_recent5y.png"
DETAILED_CYCLE_CHART_NAME = "index_margin_cycle.png"
ORIGINAL_STYLE_TITLE = "TW Margin × Index YoY Cycle"
PERCENT_CYCLE_TITLE = "TW Margin × Index YoY Percent Cycle"
STANDARDIZED_CYCLE_TITLE = "TW Margin × Index YoY Standardized Cycle"
PLOT_SMOOTHING_WINDOW = 10
ORIGINAL_STYLE_SMOOTHING_WINDOW = 5
PLOT_WINSOR_LIMIT = 5.0


def _robust_zscore_for_plot(series: pd.Series, fallback: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().sum() < 30 or numeric.nunique(dropna=True) < 3:
        return pd.to_numeric(fallback, errors="coerce")
    median = numeric.rolling(756, min_periods=60).median().fillna(numeric.expanding(min_periods=2).median())
    deviation = (numeric - median).abs()
    mad = deviation.rolling(756, min_periods=60).median().fillna(deviation.expanding(min_periods=2).median())
    zscore = 0.6745 * (numeric - median) / mad.replace(0, pd.NA)
    return zscore.fillna(pd.to_numeric(fallback, errors="coerce"))


def _margin_balance_series(df: pd.DataFrame) -> pd.Series:
    if "margin_balance_thousand_ntd" in df.columns:
        return pd.to_numeric(df["margin_balance_thousand_ntd"], errors="coerce")
    if "margin_balance" in df.columns:
        return pd.to_numeric(df["margin_balance"], errors="coerce")
    return pd.Series(pd.NA, index=df.index, dtype="Float64")


def _prepare_cycle_frame(frame: pd.DataFrame) -> pd.DataFrame:
    df = frame.copy()
    df["date"] = pd.to_datetime(df["date"])
    if "margin_balance_percentile" not in df.columns:
        df["margin_balance_percentile"] = _margin_balance_series(df).rank(pct=True) * 100
    for column in ["index_yoy_z", "margin_roc_z", "margin_balance_percentile"]:
        if column not in df.columns:
            df[column] = pd.NA
    if "final_signal" not in df.columns:
        df["final_signal"] = "NORMAL"
    return df


def prepare_percent_cycle_frame(frame: pd.DataFrame) -> pd.DataFrame:
    df = _prepare_cycle_frame(frame)
    margin_balance = _margin_balance_series(df)
    df["margin_balance"] = margin_balance
    df["index_yoy_pct"] = pd.to_numeric(df.get("index_yoy"), errors="coerce") * 100
    df["index_qoq_pct"] = pd.to_numeric(df.get("index_qoq"), errors="coerce") * 100
    df["margin_roc_pct"] = pd.to_numeric(df.get("margin_roc"), errors="coerce") * 100
    df["margin_balance_yoy"] = margin_balance / margin_balance.shift(252) - 1
    df["margin_balance_yoy_pct"] = df["margin_balance_yoy"] * 100
    return df


def prepare_original_style_frame(frame: pd.DataFrame) -> pd.DataFrame:
    df = prepare_percent_cycle_frame(frame)
    out = df[["date", "index_yoy_pct", "index_qoq_pct", "margin_balance_yoy_pct"]].copy()
    for source_column, plot_column in [
        ("index_yoy_pct", "index_yoy_pct_plot"),
        ("index_qoq_pct", "index_qoq_pct_plot"),
        ("margin_balance_yoy_pct", "margin_balance_yoy_pct_plot"),
    ]:
        out[plot_column] = (
            pd.to_numeric(out[source_column], errors="coerce")
            .rolling(ORIGINAL_STYLE_SMOOTHING_WINDOW, min_periods=1)
            .mean()
        )
    return out


def prepare_standardized_cycle_frame(frame: pd.DataFrame) -> pd.DataFrame:
    df = _prepare_cycle_frame(frame)
    df["margin_balance_percentile_z"] = df["margin_balance_percentile"] / 100 * 6 - 3
    df["index_yoy_z_chart"] = _robust_zscore_for_plot(df.get("index_yoy", df["index_yoy_z"]), df["index_yoy_z"])
    df["margin_roc_z_chart"] = _robust_zscore_for_plot(df.get("margin_roc", df["margin_roc_z"]), df["margin_roc_z"])
    for source_column, plot_column in [
        ("index_yoy_z_chart", "index_yoy_z_plot"),
        ("margin_roc_z_chart", "margin_roc_z_plot"),
        ("margin_balance_percentile_z", "margin_balance_percentile_z_plot"),
    ]:
        series = pd.to_numeric(df[source_column], errors="coerce").clip(-PLOT_WINSOR_LIMIT, PLOT_WINSOR_LIMIT)
        df[plot_column] = series.rolling(PLOT_SMOOTHING_WINDOW, min_periods=1).mean()
    return df


def signal_transition_points(df: pd.DataFrame) -> pd.DataFrame:
    signal = df["final_signal"].astype(str)
    transition = signal.ne(signal.shift(1))
    warning_signal = signal.isin(["LATE_CYCLE_LEVERAGE_WARNING", "DELEVERAGING_RISK"])
    return df.loc[transition & warning_signal].copy()


def filter_recent_years(frame: pd.DataFrame, years: int = 5) -> pd.DataFrame:
    df = frame.copy()
    df["date"] = pd.to_datetime(df["date"])
    if df.empty:
        return df
    cutoff = df["date"].max() - pd.DateOffset(years=years)
    return df[df["date"] >= cutoff].copy()


def _shade_signal_regions(ax, df: pd.DataFrame) -> None:
    color_map = {
        "LATE_CYCLE_LEVERAGE_WARNING": "#f2c94c",
        "DELEVERAGING_RISK": "#eb5757",
    }
    for signal, color in color_map.items():
        signal_df = df[df["final_signal"] == signal]
        for date in signal_df["date"]:
            ax.axvline(date, color=color, linewidth=0.8, alpha=0.18)
            ax.axvspan(date - pd.Timedelta(days=0.5), date + pd.Timedelta(days=0.5), color=color, alpha=0.06)


def _format_time_axis(ax, recent_years: int | None) -> None:
    if recent_years:
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax.xaxis.set_minor_locator(mdates.MonthLocator(interval=3))
        label_rotation = 30
    else:
        ax.xaxis.set_major_locator(mdates.YearLocator(1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.xaxis.set_minor_locator(mdates.MonthLocator(interval=3))
        label_rotation = 0
    ax.tick_params(axis="x", which="major", rotation=label_rotation)
    for label in ax.get_xticklabels(which="major"):
        label.set_ha("right" if label_rotation else "center")
    ax.grid(True, axis="x", which="major", color="#b8b8b8", linewidth=0.7, alpha=0.35)
    ax.grid(True, axis="x", which="minor", color="#d8d8d8", linewidth=0.45, alpha=0.16)


def _add_transition_markers(ax, df: pd.DataFrame, marker_y: float) -> None:
    transitions = signal_transition_points(df)
    late = transitions[transitions["final_signal"] == "LATE_CYCLE_LEVERAGE_WARNING"]
    risk = transitions[transitions["final_signal"] == "DELEVERAGING_RISK"]
    ax.scatter(
        late["date"],
        [marker_y] * len(late),
        color="#f2994a",
        marker="^",
        s=44,
        label="Late-cycle warning",
        zorder=5,
    )
    ax.scatter(
        risk["date"],
        [marker_y] * len(risk),
        color="#eb5757",
        marker="v",
        s=44,
        label="Deleveraging risk",
        zorder=5,
    )


def write_percent_cycle_chart(frame: pd.DataFrame, output_path: Path, recent_years: int | None = None) -> Path:
    ensure_dir(output_path.parent)
    df = prepare_percent_cycle_frame(frame)
    if recent_years:
        df = filter_recent_years(df, recent_years)

    fig, ax = plt.subplots(figsize=(13, 6.5))
    ax.plot(df["date"], df["index_yoy_pct"], color="#f2c94c", linewidth=1.15, label="Index YoY %")
    ax.plot(df["date"], df["margin_roc_pct"], color="#6e6e6e", linewidth=1.15, label="Margin ROC %")
    ax.plot(
        df["date"],
        df["margin_balance_yoy_pct"],
        color="#2f80ed",
        linewidth=1.05,
        label="Margin balance YoY %",
    )
    ax.axhline(0, color="#333333", linewidth=0.8, alpha=0.65)
    ax.axhline(40, color="#d65f5f", linewidth=0.8, linestyle="--", alpha=0.35)
    ax.axhline(80, color="#b23b3b", linewidth=0.8, linestyle="--", alpha=0.35)
    ax.axhline(-20, color="#7a8a99", linewidth=0.8, linestyle="--", alpha=0.4)
    ax.set_ylabel("Percentage change (%)")
    ax.set_title(PERCENT_CYCLE_TITLE)
    ax.grid(True, axis="y", alpha=0.25)

    values = df[["index_yoy_pct", "margin_roc_pct", "margin_balance_yoy_pct"]].stack().dropna()
    data_min = min(float(values.min()) if not values.empty else 0.0, -20.0)
    data_max = max(float(values.max()) if not values.empty else 80.0, 80.0)
    padding = max((data_max - data_min) * 0.08, 8.0)
    marker_y = data_max + padding * 0.35
    _add_transition_markers(ax, df, marker_y)
    ax.set_ylim(data_min - padding, data_max + padding)

    _format_time_axis(ax, recent_years)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.12), ncols=5, fontsize=9, frameon=False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def write_original_style_chart(frame: pd.DataFrame, output_path: Path, recent_years: int | None = None) -> Path:
    ensure_dir(output_path.parent)
    df = prepare_original_style_frame(frame)
    if recent_years:
        df = filter_recent_years(df, recent_years)

    fig, ax = plt.subplots(figsize=(14.5, 7.2))
    ax.plot(df["date"], df["index_yoy_pct_plot"], color="#c9914b", linewidth=0.85, alpha=0.88, label="Index YoY %")
    ax.plot(
        df["date"],
        df["margin_balance_yoy_pct_plot"],
        color="#9c9c9c",
        linewidth=0.85,
        alpha=0.82,
        label="Margin YoY %",
    )
    ax.plot(
        df["date"],
        df["index_qoq_pct_plot"],
        color="#5f84ad",
        linewidth=0.85,
        alpha=0.86,
        label="Index QoQ %",
    )
    ax.axhline(0, color="#777777", linewidth=0.75, alpha=0.55)
    ax.set_ylabel("Percentage change (%)", fontsize=9, color="#444444")
    ax.set_title(ORIGINAL_STYLE_TITLE, fontsize=10, pad=10)
    ax.grid(True, axis="y", color="#d9d9d9", linewidth=0.7, alpha=0.34)
    _format_time_axis(ax, recent_years)
    ax.grid(False, axis="x", which="major")
    ax.grid(False, axis="x", which="minor")
    ax.tick_params(axis="both", labelsize=8, colors="#555555")
    ax.tick_params(axis="x", which="minor", length=2.5, color="#c8c8c8")
    ax.tick_params(axis="x", which="major", length=4, color="#999999")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#d0d0d0")
    ax.spines["bottom"].set_color("#d0d0d0")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.035), ncols=3, fontsize=7.5, frameon=False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def write_standardized_cycle_chart(frame: pd.DataFrame, output_path: Path, recent_years: int | None = None) -> Path:
    ensure_dir(output_path.parent)
    df = prepare_standardized_cycle_frame(frame)
    if recent_years:
        df = filter_recent_years(df, recent_years)

    fig, ax = plt.subplots(figsize=(13, 6.5))
    ax.plot(df["date"], df["index_yoy_z_plot"], color="#f2c94c", linewidth=1.15, label="Index YoY z-score")
    ax.plot(df["date"], df["margin_roc_z_plot"], color="#6e6e6e", linewidth=1.15, label="Margin ROC z-score")
    ax.plot(
        df["date"],
        df["margin_balance_percentile_z_plot"],
        color="#2f80ed",
        linewidth=1.05,
        label="Margin balance percentile z",
    )
    ax.axhline(0, color="#333333", linewidth=0.8, alpha=0.6)
    ax.axhline(2, color="#d65f5f", linewidth=0.8, linestyle="--", alpha=0.45)
    ax.axhline(-2, color="#7a8a99", linewidth=0.8, linestyle="--", alpha=0.45)
    ax.set_ylim(-3.5, 3.5)
    ax.set_ylabel("Standardized score")
    ax.set_title(STANDARDIZED_CYCLE_TITLE)
    ax.grid(True, axis="y", alpha=0.25)

    _add_transition_markers(ax, df, 3.1)

    _format_time_axis(ax, recent_years)
    ax.legend(loc="upper left", ncols=2)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def write_index_margin_chart(frame: pd.DataFrame, output_path: Path) -> Path:
    ensure_dir(output_path.parent)
    df = frame.copy()
    df["date"] = pd.to_datetime(df["date"])
    fig, axes = plt.subplots(CHART_PANEL_COUNT, 1, figsize=(13, 9), sharex=True)
    ax_growth, ax_balance, ax_margin = axes

    ax_growth.plot(df["date"], df["index_yoy"], color="#f2c94c", label="Index YoY")
    ax_growth.plot(df["date"], df["index_qoq"], color="#2f80ed", label="Index QoQ")
    ax_growth.axhline(0, color="#444444", linewidth=0.8, alpha=0.5)
    ax_growth.set_ylabel("Index growth")
    ax_growth.legend(loc="upper left")
    ax_growth.grid(True, axis="y", alpha=0.25)

    ax_balance.plot(df["date"], df["margin_balance_thousand_ntd"], color="#111111", linewidth=1.1, label="Margin balance")
    ax_balance.set_ylabel("Margin balance")
    ax_balance.legend(loc="upper left")
    ax_balance.grid(True, axis="y", alpha=0.25)

    ax_margin.plot(df["date"], df["margin_roc"], color="#777777", label="Margin ROC")
    ax_margin.axhline(0, color="#444444", linewidth=0.8, alpha=0.5)
    if "final_signal" in df:
        warning = df[df["final_signal"].astype(str).str.contains("WARNING|RISK", regex=True, na=False)]
        ax_margin.scatter(warning["date"], warning["margin_roc"], color="#d62728", s=25, label="warning marker")
    ax_margin.set_ylabel("Margin ROC")
    ax_margin.legend(loc="upper left")
    ax_margin.grid(True, axis="y", alpha=0.25)

    ax_growth.set_title("TW Index-Margin Cycle")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path
