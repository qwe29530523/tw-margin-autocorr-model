from __future__ import annotations

import argparse
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests


TWSE_INDEX_URL = "https://wwwc.twse.com.tw/indicesReport/MI_5MINS_HIST"
TWSE_MARGIN_URL = "https://wwwc.twse.com.tw/exchangeReport/MI_MARGN"
USER_AGENT = "tw-margin-autocorr-model/1.0"


@dataclass(frozen=True)
class ModelConfig:
    start: date
    end: date
    index_yoy_window: int
    index_qoq_window: int
    margin_roc_window: int
    autocorr_window: int
    threshold_quantile: float
    output_dir: Path
    force_refresh: bool
    max_workers: int
    request_delay: float


def parse_args() -> ModelConfig:
    today_tw = datetime.now(ZoneInfo("Asia/Taipei")).date()
    parser = argparse.ArgumentParser(
        description="Track TAIEX growth and Taiwan market margin balance ROC autocorrelation."
    )
    parser.add_argument("--start", default="2012-01-01", help="Start date, YYYY-MM-DD.")
    parser.add_argument("--end", default=today_tw.isoformat(), help="End date, YYYY-MM-DD.")
    parser.add_argument("--index-yoy-window", type=int, default=252)
    parser.add_argument("--index-qoq-window", type=int, default=63)
    parser.add_argument("--margin-roc-window", type=int, default=63)
    parser.add_argument("--autocorr-window", type=int, default=126)
    parser.add_argument("--threshold-quantile", type=float, default=0.90)
    parser.add_argument("--output-dir", default="output")
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Ignore existing output CSV cache and refetch all margin observations.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Concurrent workers for daily margin API calls.",
    )
    parser.add_argument(
        "--request-delay",
        type=float,
        default=0.0,
        help="Optional delay before each margin request, in seconds.",
    )
    args = parser.parse_args()

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()
    if start > end:
        raise ValueError("--start must be before or equal to --end")
    if not 0 < args.threshold_quantile < 1:
        raise ValueError("--threshold-quantile must be between 0 and 1")
    for name in (
        "index_yoy_window",
        "index_qoq_window",
        "margin_roc_window",
        "autocorr_window",
        "max_workers",
    ):
        if getattr(args, name) <= 0:
            raise ValueError(f"--{name.replace('_', '-')} must be positive")

    return ModelConfig(
        start=start,
        end=end,
        index_yoy_window=args.index_yoy_window,
        index_qoq_window=args.index_qoq_window,
        margin_roc_window=args.margin_roc_window,
        autocorr_window=args.autocorr_window,
        threshold_quantile=args.threshold_quantile,
        output_dir=Path(args.output_dir),
        force_refresh=args.force_refresh,
        max_workers=args.max_workers,
        request_delay=args.request_delay,
    )


def request_json(url: str, params: dict[str, Any], retries: int = 3) -> dict[str, Any]:
    headers = {"User-Agent": USER_AGENT}
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < retries:
                time.sleep(0.7 * attempt)
    raise RuntimeError(f"Failed to fetch {url} with params={params}: {last_error}")


def parse_number(value: Any) -> float:
    if value is None:
        return math.nan
    text = str(value).strip().replace(",", "")
    if text in {"", "--", "X"}:
        return math.nan
    return float(text)


def parse_twse_date(value: Any) -> pd.Timestamp:
    text = str(value).strip()
    if "/" in text:
        year_text, month_text, day_text = text.split("/")
        year = int(year_text) + 1911
        return pd.Timestamp(year=year, month=int(month_text), day=int(day_text))
    if len(text) == 7 and text.isdigit():
        year = int(text[:3]) + 1911
        return pd.Timestamp(year=year, month=int(text[3:5]), day=int(text[5:7]))
    return pd.Timestamp(text)


def month_starts(start: date, end: date) -> list[date]:
    current = date(start.year, start.month, 1)
    months: list[date] = []
    while current <= end:
        months.append(current)
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return months


def parse_index_payload(month_start: date, payload: dict[str, Any]) -> pd.DataFrame:
    if payload.get("stat") != "OK" or not payload.get("data"):
        raise ValueError(f"TWSE index data unavailable: {payload}")
    fields = payload["fields"]
    rows = payload["data"]
    month_df = pd.DataFrame(rows, columns=fields)
    month_df = month_df.rename(
        columns={
            "日期": "date",
            "開盤指數": "index_open",
            "最高指數": "index_high",
            "最低指數": "index_low",
            "收盤指數": "index_close",
        }
    )
    month_df["date"] = month_df["date"].map(parse_twse_date)
    same_month = (month_df["date"].dt.year == month_start.year) & (
        month_df["date"].dt.month == month_start.month
    )
    if not bool(same_month.all()):
        observed = ", ".join(sorted(month_df["date"].dt.strftime("%Y-%m").unique()))
        raise ValueError(f"Expected {month_start:%Y-%m}, got {observed}")
    for column in ["index_open", "index_high", "index_low", "index_close"]:
        month_df[column] = month_df[column].map(parse_number)
    return month_df[["date", "index_open", "index_high", "index_low", "index_close"]]


def fetch_index_month(month_start: date, retries: int = 4) -> pd.DataFrame:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            payload = request_json(
                TWSE_INDEX_URL,
                {"response": "json", "date": month_start.strftime("%Y%m%d")},
            )
            return parse_index_payload(month_start, payload)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        if attempt < retries:
            time.sleep(0.7 * attempt)
    raise RuntimeError(f"TWSE index data unavailable for {month_start:%Y-%m}: {last_error}")


def fetch_index_history(start: date, end: date, max_workers: int) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    failed_months: list[str] = []
    months = month_starts(start, end)
    print(f"Fetching {len(months)} TWSE monthly TAIEX files...", flush=True)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_index_month, month_start): month_start for month_start in months}
        for idx, future in enumerate(as_completed(futures), start=1):
            month_start = futures[future]
            try:
                month_df = future.result()
            except Exception as exc:  # noqa: BLE001
                print(f"Warning: index fetch failed for {month_start:%Y-%m}: {exc}", flush=True)
                failed_months.append(month_start.strftime("%Y-%m"))
                month_df = None
            if month_df is not None:
                frames.append(month_df)
            if idx % 24 == 0 or idx == len(months):
                print(f"  index progress: {idx}/{len(months)}", flush=True)

    if failed_months:
        raise RuntimeError(f"Missing TWSE index month(s): {', '.join(failed_months)}")
    if not frames:
        raise RuntimeError("No TAIEX index data was returned from TWSE.")

    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["date"]).sort_values("date")
    mask = (df["date"].dt.date >= start) & (df["date"].dt.date <= end)
    df = df.loc[mask].reset_index(drop=True)
    if df.empty:
        raise RuntimeError("TAIEX index data is empty after date filtering.")
    return df


def parse_margin_payload(payload: dict[str, Any], query_date: pd.Timestamp) -> dict[str, Any] | None:
    if payload.get("stat") != "OK":
        return None
    for table in payload.get("tables", []):
        fields = table.get("fields") or []
        rows = table.get("data") or []
        if "項目" not in fields or "今日餘額" not in fields:
            continue
        item_idx = fields.index("項目")
        balance_idx = fields.index("今日餘額")
        previous_idx = fields.index("前日餘額") if "前日餘額" in fields else None
        for row in rows:
            item = str(row[item_idx]).strip()
            if item == "融資金額(仟元)":
                return {
                    "date": query_date,
                    "margin_balance_thousand_ntd": parse_number(row[balance_idx]),
                    "margin_previous_balance_thousand_ntd": (
                        parse_number(row[previous_idx]) if previous_idx is not None else math.nan
                    ),
                }
    return None


def fetch_margin_for_date(
    query_date: pd.Timestamp, request_delay: float = 0.0, retries: int = 4
) -> dict[str, Any]:
    payload: dict[str, Any] | None = None
    for attempt in range(1, retries + 1):
        if request_delay > 0:
            time.sleep(request_delay)
        payload = request_json(
            TWSE_MARGIN_URL,
            {
                "response": "json",
                "date": query_date.strftime("%Y%m%d"),
                "selectType": "MS",
            },
        )
        row = parse_margin_payload(payload, query_date)
        if row is not None:
            return row
        if attempt < retries:
            time.sleep(0.7 * attempt)
    raise RuntimeError(f"TWSE margin data unavailable for {query_date.date()}: {payload}")


def load_cached_margin(output_csv: Path, force_refresh: bool) -> pd.DataFrame:
    columns = ["date", "margin_balance_thousand_ntd", "margin_previous_balance_thousand_ntd"]
    if force_refresh or not output_csv.exists():
        return pd.DataFrame(columns=columns)
    try:
        cached = pd.read_csv(output_csv, parse_dates=["date"])
    except Exception:  # noqa: BLE001
        return pd.DataFrame(columns=columns)
    if not {"date", "margin_balance_thousand_ntd"}.issubset(cached.columns):
        return pd.DataFrame(columns=columns)
    for column in columns:
        if column not in cached.columns:
            cached[column] = math.nan
    return cached[columns].dropna(subset=["margin_balance_thousand_ntd"])


def fetch_margin_history(index_dates: pd.Series, config: ModelConfig, output_csv: Path) -> pd.DataFrame:
    cached = load_cached_margin(output_csv, config.force_refresh)
    cached_dates = set(pd.to_datetime(cached["date"]).dt.strftime("%Y-%m-%d")) if not cached.empty else set()
    wanted_dates = pd.to_datetime(index_dates).drop_duplicates().sort_values()
    missing_dates = [
        timestamp for timestamp in wanted_dates if timestamp.strftime("%Y-%m-%d") not in cached_dates
    ]

    rows: list[dict[str, Any]] = []
    failed_dates: list[str] = []
    if missing_dates:
        print(f"Fetching {len(missing_dates)} TWSE daily margin observations...", flush=True)
        with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
            futures = {
                executor.submit(fetch_margin_for_date, query_date, config.request_delay): query_date
                for query_date in missing_dates
            }
            for idx, future in enumerate(as_completed(futures), start=1):
                query_date = futures[future]
                try:
                    row = future.result()
                except Exception as exc:  # noqa: BLE001
                    print(f"Warning: margin fetch failed for {query_date.date()}: {exc}", flush=True)
                    failed_dates.append(query_date.strftime("%Y-%m-%d"))
                    row = None
                if row is not None:
                    rows.append(row)
                if idx % 100 == 0 or idx == len(missing_dates):
                    print(f"  margin progress: {idx}/{len(missing_dates)}", flush=True)

    if failed_dates:
        raise RuntimeError(f"Missing TWSE margin date(s): {', '.join(failed_dates[:20])}")
    fetched = pd.DataFrame(rows)
    combined = pd.concat([cached, fetched], ignore_index=True)
    if combined.empty:
        raise RuntimeError("No margin balance data was available.")
    combined["date"] = pd.to_datetime(combined["date"])
    combined = combined.dropna(subset=["margin_balance_thousand_ntd"])
    combined = combined.drop_duplicates(subset=["date"], keep="last").sort_values("date")
    return combined.reset_index(drop=True)


def rolling_lag1_autocorr(series: pd.Series, window: int) -> pd.Series:
    def corr(values: np.ndarray) -> float:
        clean = pd.Series(values).dropna()
        if len(clean) < window:
            return math.nan
        return float(clean.autocorr(lag=1))

    return series.rolling(window=window, min_periods=window).apply(corr, raw=True)


def assign_signals(df: pd.DataFrame) -> pd.Series:
    high = df["margin_roc_autocorr"] >= df["autocorr_high_threshold"]
    margin_up = df["margin_roc"] > 0
    margin_down = df["margin_roc"] < 0
    qoq_up = df["index_qoq"] > 0
    qoq_down = df["index_qoq"] < 0
    yoy_up = df["index_yoy"] > 0

    signal = pd.Series("NORMAL", index=df.index, dtype="object")
    signal.loc[high & margin_up & qoq_up] = "HOT_LEVERAGE_MOMENTUM"
    signal.loc[high & margin_up & qoq_down & yoy_up] = "LATE_CYCLE_LEVERAGE_WARNING"
    signal.loc[high & margin_down & qoq_down] = "DELEVERAGING_RISK"
    return signal


def build_model_frame(index_df: pd.DataFrame, margin_df: pd.DataFrame, config: ModelConfig) -> pd.DataFrame:
    df = pd.merge(index_df, margin_df, on="date", how="inner").sort_values("date").reset_index(drop=True)
    if df.empty:
        raise RuntimeError("Merged dataframe is empty.")

    df["index_yoy"] = df["index_close"] / df["index_close"].shift(config.index_yoy_window) - 1
    df["index_qoq"] = df["index_close"] / df["index_close"].shift(config.index_qoq_window) - 1
    df["margin_roc"] = (
        df["margin_balance_thousand_ntd"]
        / df["margin_balance_thousand_ntd"].shift(config.margin_roc_window)
        - 1
    )
    df["margin_roc_autocorr"] = rolling_lag1_autocorr(df["margin_roc"], config.autocorr_window)
    threshold = df["margin_roc_autocorr"].quantile(config.threshold_quantile)
    df["autocorr_high_threshold"] = threshold
    df["is_autocorr_high"] = df["margin_roc_autocorr"] >= threshold
    df["signal"] = assign_signals(df)
    return df


def plot_growth(df: pd.DataFrame, output_path: Path) -> None:
    plot_df = df.dropna(subset=["index_yoy", "index_qoq", "margin_roc"])
    fig, ax = plt.subplots(figsize=(14, 7))
    ax.plot(plot_df["date"], plot_df["index_yoy"] * 100, color="#f2c94c", linewidth=1.7, label="Index YoY")
    ax.plot(plot_df["date"], plot_df["index_qoq"] * 100, color="#2f80ed", linewidth=1.4, label="Index QoQ")
    ax.plot(plot_df["date"], plot_df["margin_roc"] * 100, color="#8c8c8c", linewidth=1.2, label="Margin ROC")
    ax.axhline(0, color="#333333", linewidth=0.8, alpha=0.6)
    ax.set_title("TAIEX Growth and Margin Balance ROC")
    ax.set_ylabel("Percent")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(loc="upper left")
    ax.xaxis.set_major_locator(mdates.YearLocator(1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def plot_signals(df: pd.DataFrame, output_path: Path) -> None:
    signal_colors = {
        "HOT_LEVERAGE_MOMENTUM": "#d62728",
        "LATE_CYCLE_LEVERAGE_WARNING": "#ff7f0e",
        "DELEVERAGING_RISK": "#1f77b4",
    }
    fig, (ax_price, ax_auto) = plt.subplots(
        2, 1, figsize=(14, 9), sharex=True, gridspec_kw={"height_ratios": [2, 1]}
    )

    ax_price.plot(df["date"], df["index_close"], color="#222222", linewidth=1.4, label="TAIEX close")
    for signal, color in signal_colors.items():
        points = df[df["signal"] == signal]
        ax_price.scatter(points["date"], points["index_close"], s=18, color=color, label=signal, alpha=0.8)
    ax_price.set_title("TAIEX and Margin Autocorrelation Signals")
    ax_price.set_ylabel("Index")
    ax_price.grid(True, axis="y", alpha=0.25)
    ax_price.legend(loc="upper left", ncols=2)

    ax_auto.plot(df["date"], df["margin_roc_autocorr"], color="#6f42c1", linewidth=1.2, label="Margin ROC autocorr")
    if df["autocorr_high_threshold"].notna().any():
        threshold = float(df["autocorr_high_threshold"].dropna().iloc[-1])
        ax_auto.axhline(threshold, color="#d62728", linewidth=1.0, linestyle="--", label="High threshold")
    ax_auto.set_ylabel("Autocorr")
    ax_auto.grid(True, axis="y", alpha=0.25)
    ax_auto.legend(loc="upper left")
    ax_auto.xaxis.set_major_locator(mdates.YearLocator(1))
    ax_auto.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def json_safe(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        if math.isnan(float(value)):
            return None
        return float(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def write_summary(df: pd.DataFrame, config: ModelConfig, output_path: Path) -> None:
    latest = df.dropna(subset=["index_close", "margin_balance_thousand_ntd"]).iloc[-1]
    signal_counts = df["signal"].value_counts(dropna=False).to_dict()
    summary = {
        "generated_at": datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
        "data_start": df["date"].min().date().isoformat(),
        "data_end": df["date"].max().date().isoformat(),
        "rows": int(len(df)),
        "latest": {
            "date": latest["date"].date().isoformat(),
            "signal": latest["signal"],
            "index_close": latest["index_close"],
            "index_yoy": latest["index_yoy"],
            "index_qoq": latest["index_qoq"],
            "margin_balance_thousand_ntd": latest["margin_balance_thousand_ntd"],
            "margin_roc": latest["margin_roc"],
            "margin_roc_autocorr": latest["margin_roc_autocorr"],
            "autocorr_high_threshold": latest["autocorr_high_threshold"],
        },
        "signal_counts": signal_counts,
        "parameters": {
            "start": config.start,
            "end": config.end,
            "index_yoy_window": config.index_yoy_window,
            "index_qoq_window": config.index_qoq_window,
            "margin_roc_window": config.margin_roc_window,
            "autocorr_window": config.autocorr_window,
            "threshold_quantile": config.threshold_quantile,
        },
        "data_sources": {
            "taiex": TWSE_INDEX_URL,
            "margin": TWSE_MARGIN_URL,
        },
    }
    output_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=json_safe),
        encoding="utf-8",
    )


def write_outputs(df: pd.DataFrame, config: ModelConfig) -> None:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = config.output_dir / "tw_margin_autocorr_model.csv"
    growth_path = config.output_dir / "tw_margin_autocorr_growth.png"
    signal_path = config.output_dir / "tw_margin_autocorr_signal.png"
    summary_path = config.output_dir / "signal_summary.json"

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    plot_growth(df, growth_path)
    plot_signals(df, signal_path)
    write_summary(df, config, summary_path)

    print(f"Wrote {csv_path}", flush=True)
    print(f"Wrote {growth_path}", flush=True)
    print(f"Wrote {signal_path}", flush=True)
    print(f"Wrote {summary_path}", flush=True)


def main() -> None:
    config = parse_args()
    output_csv = config.output_dir / "tw_margin_autocorr_model.csv"
    print(f"Fetching TAIEX index data from {config.start} to {config.end}...", flush=True)
    index_df = fetch_index_history(config.start, config.end, config.max_workers)
    print(f"Fetched {len(index_df)} index observations.", flush=True)
    margin_df = fetch_margin_history(index_df["date"], config, output_csv)
    print(f"Available margin observations: {len(margin_df)}", flush=True)
    model_df = build_model_frame(index_df, margin_df, config)
    write_outputs(model_df, config)


if __name__ == "__main__":
    main()
