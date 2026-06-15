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
DATA_QUALITY_COLUMNS = [
    "date",
    "taiex_close",
    "margin_balance",
    "index_yoy",
    "index_qoq",
    "margin_roc",
    "reason",
]
MARKET_EXTREME_COLUMNS = [
    "date",
    "taiex_close",
    "margin_balance",
    "index_yoy",
    "index_qoq",
    "margin_roc",
    "index_yoy_z",
    "index_qoq_z",
    "margin_roc_z",
    "margin_roc_autocorr",
    "margin_roc_autocorr_z",
    "margin_roc_autocorr_percentile",
    "margin_roc_autocorr_percentile_full_sample",
    "margin_roc_autocorr_rank_252",
    "margin_roc_persistence_score",
    "autocorr_high_threshold",
    "reason",
]
OUTLIER_CONTEXT_COLUMNS = [
    "outlier_date",
    "context_date",
    "taiex_close",
    "margin_balance",
    "index_yoy",
    "index_qoq",
    "margin_roc",
]


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
    payload_date = payload.get("date")
    if not payload_date:
        raise ValueError(f"TWSE margin payload missing date for {query_date.date()}")
    actual_date = pd.Timestamp(datetime.strptime(str(payload_date), "%Y%m%d").date())
    if actual_date != query_date.normalize():
        raise ValueError(
            f"TWSE margin payload date mismatch: requested {query_date.date()}, got {actual_date.date()}"
        )
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


def remove_isolated_cached_margin_outliers(cached: pd.DataFrame, jump_threshold: float = 0.20) -> pd.DataFrame:
    if cached.empty:
        return cached
    cached = cached.copy()
    cached["date"] = pd.to_datetime(cached["date"])
    cached["margin_balance_thousand_ntd"] = pd.to_numeric(
        cached["margin_balance_thousand_ntd"], errors="coerce"
    )
    cached = cached.dropna(subset=["margin_balance_thousand_ntd"])
    cached = cached.drop_duplicates(subset=["date"], keep="last").sort_values("date")

    balance = cached["margin_balance_thousand_ntd"]
    prev_jump = (balance / balance.shift(1) - 1).abs()
    next_jump = (balance / balance.shift(-1) - 1).abs()
    isolated_outlier = (prev_jump > jump_threshold) & (next_jump > jump_threshold)
    if isolated_outlier.any():
        dates = cached.loc[isolated_outlier, "date"].dt.strftime("%Y-%m-%d").tolist()
        print(
            "Dropping isolated cached margin outlier(s) for refetch: "
            + ", ".join(dates[:20]),
            flush=True,
        )
    return cached.loc[~isolated_outlier].reset_index(drop=True)


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
    return remove_isolated_cached_margin_outliers(cached[columns])


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


def robust_zscore(series: pd.Series, window: int = 756, min_periods: int = 126, clip: float = 3.0) -> pd.Series:
    median = series.rolling(window, min_periods=min_periods).median()
    expanding_median = series.expanding(min_periods=2).median()
    median = median.fillna(expanding_median)

    absolute_deviation = (series - median).abs()
    mad = absolute_deviation.rolling(window, min_periods=min_periods).median()
    expanding_mad = absolute_deviation.expanding(min_periods=2).median()
    mad = mad.fillna(expanding_mad)

    z = 0.6745 * (series - median) / mad.replace(0, np.nan)
    return z.clip(-clip, clip)


def expanding_percentile(series: pd.Series) -> pd.Series:
    values: list[float] = []
    percentiles: list[float] = []
    for value in series:
        if pd.isna(value):
            percentiles.append(math.nan)
            continue
        numeric_value = float(value)
        values.append(numeric_value)
        sample = np.asarray(values)
        percentiles.append(float((sample <= numeric_value).mean()))
    return pd.Series(percentiles, index=series.index)


def full_sample_percentile(series: pd.Series) -> pd.Series:
    return series.rank(method="max", pct=True)


def rolling_percentile_rank(series: pd.Series, window: int = 252, min_periods: int = 1) -> pd.Series:
    valid_values: list[float] = []
    ranks: list[float] = []
    for value in series:
        if pd.isna(value):
            ranks.append(math.nan)
            continue
        numeric_value = float(value)
        valid_values.append(numeric_value)
        sample = np.asarray(valid_values[-window:])
        if len(sample) < min_periods:
            ranks.append(math.nan)
        else:
            ranks.append(float((sample <= numeric_value).mean()))
    return pd.Series(ranks, index=series.index)


def margin_roc_persistence_score(
    margin_roc: pd.Series,
    margin_roc_z: pd.Series,
    window: int = 20,
) -> pd.Series:
    positive_ratio = (margin_roc > 0).rolling(window, min_periods=window).mean()
    high_z_ratio = (margin_roc_z > 1).rolling(window, min_periods=window).mean()
    return (positive_ratio + high_z_ratio) / 2


def is_price_and_margin_factor_extreme(row: pd.Series) -> bool:
    return bool(
        (row.get("index_yoy_z", math.nan) > 2.0)
        and (row.get("index_qoq_z", math.nan) > 2.0)
        and (row.get("margin_roc_z", math.nan) > 2.0)
    )


def derive_final_signal_and_reason(row: pd.Series) -> tuple[str, str]:
    raw_signal = str(row.get("raw_signal", row.get("signal", "NORMAL")))
    factor_extreme = is_price_and_margin_factor_extreme(row)
    high_autocorr_rank = row.get("margin_roc_autocorr_rank_252", math.nan) > 0.90
    high_persistence = row.get("margin_roc_persistence_score", math.nan) > 0.70

    if factor_extreme and (high_autocorr_rank or high_persistence):
        reason_parts = ["price_and_margin_factor_extreme"]
        if high_autocorr_rank:
            reason_parts.append("autocorr_rank_252_gt_90pct")
        if high_persistence:
            reason_parts.append("persistence_gt_70pct")
        return "LATE_CYCLE_LEVERAGE_WARNING", "; ".join(reason_parts)
    if factor_extreme:
        return (
            "PRICE_AND_MARGIN_EXTREME",
            "price_and_margin_factor_extreme; waiting_for_autocorr_or_persistence_confirmation",
        )
    return raw_signal, f"raw_signal={raw_signal}"


def derive_latest_signal(latest: pd.Series) -> str:
    if "final_signal" in latest:
        return str(latest.get("final_signal", "NORMAL"))
    return derive_final_signal_and_reason(latest)[0]


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


def leverage_cycle_phase_from_signal(signal: str) -> str:
    if signal in {"HOT_LEVERAGE_MOMENTUM", "PRICE_AND_MARGIN_EXTREME"}:
        return "hot_leverage_momentum"
    if signal == "LATE_CYCLE_LEVERAGE_WARNING":
        return "late_cycle_leverage_warning"
    if signal == "DELEVERAGING_RISK":
        return "deleveraging_risk"
    return "normal"


def assign_transition_watch(df: pd.DataFrame) -> pd.Series:
    qoq_turning_weaker = df["index_qoq_change_20d"] < 0
    margin_still_high = (df["margin_roc"] > 0) & (df["margin_roc_z"] > 1.0)
    distribution_warning = qoq_turning_weaker & margin_still_high

    deleveraging_risk_watch = (df["index_close_return_20d"] < 0) & (df["margin_roc_change_20d"] < 0)

    transition_watch = pd.Series("none", index=df.index, dtype="object")
    transition_watch.loc[distribution_warning] = "distribution_warning"
    transition_watch.loc[deleveraging_risk_watch] = "deleveraging_risk_watch"
    return transition_watch


def assign_signal_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["index_close_return_20d"] = out["index_close"].pct_change(20)
    out["index_qoq_change_20d"] = out["index_qoq"].diff(20)
    out["margin_roc_change_20d"] = out["margin_roc"].diff(20)
    out["raw_signal"] = assign_signals(out)
    out["transition_watch"] = assign_transition_watch(out)

    derived = out.apply(derive_final_signal_and_reason, axis=1, result_type="expand")
    out["final_signal"] = derived[0]
    out["final_signal_reason"] = derived[1]
    has_transition_watch = out["transition_watch"] != "none"
    out.loc[has_transition_watch, "final_signal_reason"] = (
        out.loc[has_transition_watch, "final_signal_reason"]
        + "; transition_watch="
        + out.loc[has_transition_watch, "transition_watch"]
    )
    out["leverage_cycle_phase"] = out["final_signal"].map(leverage_cycle_phase_from_signal)
    out["signal"] = out["final_signal"]
    return out


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
    df["index_yoy_z"] = robust_zscore(df["index_yoy"])
    df["index_qoq_z"] = robust_zscore(df["index_qoq"])
    df["margin_roc_z"] = robust_zscore(df["margin_roc"])
    df["margin_roc_autocorr_z"] = robust_zscore(df["margin_roc_autocorr"])
    df["margin_roc_autocorr_percentile_full_sample"] = full_sample_percentile(df["margin_roc_autocorr"])
    df["margin_roc_autocorr_percentile"] = df["margin_roc_autocorr_percentile_full_sample"]
    df["margin_roc_autocorr_rank_252"] = rolling_percentile_rank(df["margin_roc_autocorr"], window=252)
    df["margin_roc_persistence_score"] = margin_roc_persistence_score(df["margin_roc"], df["margin_roc_z"])
    df["margin_roc_autocorr_plot"] = df["margin_roc_autocorr_rank_252"].clip(0, 1)
    df["index_yoy_z_plot"] = df["index_yoy_z"].ewm(span=20, adjust=False).mean().clip(-3, 3)
    df["index_qoq_z_plot"] = df["index_qoq_z"].ewm(span=20, adjust=False).mean().clip(-3, 3)
    df["margin_roc_z_plot"] = df["margin_roc_z"].ewm(span=20, adjust=False).mean().clip(-3, 3)
    df["margin_roc_autocorr_bar"] = ((df["margin_roc_autocorr_rank_252"] - 0.5) * 2).clip(-1, 1)
    df["index_yoy_ref"] = df["index_yoy_z"].ewm(span=30, adjust=False).mean().clip(-2.5, 2.5)
    df["index_qoq_ref"] = df["index_qoq_z"].ewm(span=20, adjust=False).mean().clip(-2.5, 2.5)
    df["margin_roc_ref"] = df["margin_roc_z"].ewm(span=20, adjust=False).mean().clip(-2.5, 2.5)
    df["autocorr_bar"] = ((df["margin_roc_autocorr_rank_252"] - 0.5) * 2).clip(-1, 1)
    return assign_signal_columns(df)


def diagnostic_source_frame(
    index_df: pd.DataFrame, margin_df: pd.DataFrame, model_df: pd.DataFrame
) -> pd.DataFrame:
    index_source = index_df[["date", "index_close"]].copy()
    margin_source = margin_df[["date", "margin_balance_thousand_ntd"]].copy()
    source = pd.merge(index_source, margin_source, on="date", how="outer", indicator=True)
    features = model_df[
        [
            "date",
            "index_yoy",
            "index_qoq",
            "margin_roc",
            "index_yoy_z",
            "index_qoq_z",
            "margin_roc_z",
            "margin_roc_autocorr",
            "margin_roc_autocorr_z",
            "margin_roc_autocorr_percentile",
            "margin_roc_autocorr_percentile_full_sample",
            "margin_roc_autocorr_rank_252",
            "margin_roc_persistence_score",
            "margin_roc_autocorr_plot",
            "autocorr_high_threshold",
        ]
    ].copy()
    diagnostic = pd.merge(source, features, on="date", how="left")
    diagnostic = diagnostic.rename(
        columns={
            "index_close": "taiex_close",
            "margin_balance_thousand_ntd": "margin_balance",
        }
    )
    return diagnostic.sort_values("date").reset_index(drop=True)


def add_diagnostic_reason(
    reasons: dict[pd.Timestamp, list[str]],
    diagnostic: pd.DataFrame,
    mask: pd.Series,
    reason: str,
) -> None:
    dates = pd.to_datetime(diagnostic.loc[mask.fillna(False), "date"])
    for item in dates:
        reasons.setdefault(item.normalize(), []).append(reason)


def reasons_to_report(
    diagnostic: pd.DataFrame,
    reasons: dict[pd.Timestamp, list[str]],
    columns: list[str],
) -> pd.DataFrame:
    if not reasons:
        return pd.DataFrame(columns=columns)

    diagnostic_by_date = diagnostic.drop_duplicates(subset=["date"], keep="last").set_index("date")
    rows: list[dict[str, Any]] = []
    for outlier_date in sorted(reasons):
        source_row = diagnostic_by_date.loc[outlier_date]
        row = {
            "date": outlier_date,
            "taiex_close": source_row.get("taiex_close", math.nan),
            "margin_balance": source_row.get("margin_balance", math.nan),
            "index_yoy": source_row.get("index_yoy", math.nan),
            "index_qoq": source_row.get("index_qoq", math.nan),
            "margin_roc": source_row.get("margin_roc", math.nan),
            "index_yoy_z": source_row.get("index_yoy_z", math.nan),
            "index_qoq_z": source_row.get("index_qoq_z", math.nan),
            "margin_roc_z": source_row.get("margin_roc_z", math.nan),
            "margin_roc_autocorr": source_row.get("margin_roc_autocorr", math.nan),
            "margin_roc_autocorr_z": source_row.get("margin_roc_autocorr_z", math.nan),
            "margin_roc_autocorr_percentile": source_row.get("margin_roc_autocorr_percentile", math.nan),
            "margin_roc_autocorr_percentile_full_sample": source_row.get(
                "margin_roc_autocorr_percentile_full_sample", math.nan
            ),
            "margin_roc_autocorr_rank_252": source_row.get("margin_roc_autocorr_rank_252", math.nan),
            "margin_roc_persistence_score": source_row.get("margin_roc_persistence_score", math.nan),
            "margin_roc_autocorr_plot": source_row.get("margin_roc_autocorr_plot", math.nan),
            "autocorr_high_threshold": source_row.get("autocorr_high_threshold", math.nan),
            "reason": ";".join(sorted(set(reasons[outlier_date]))),
        }
        rows.append({column: row.get(column, math.nan) for column in columns})
    return pd.DataFrame(rows, columns=columns)


def verify_taiex_close(query_date: pd.Timestamp, observed_close: float) -> bool:
    try:
        month_df = fetch_index_month(date(query_date.year, query_date.month, 1))
    except Exception as exc:  # noqa: BLE001
        print(f"Warning: unable to verify TAIEX close for {query_date.date()}: {exc}", flush=True)
        return False
    matched = month_df.loc[month_df["date"].dt.normalize() == query_date.normalize(), "index_close"]
    return bool(not matched.empty and np.isclose(float(matched.iloc[0]), float(observed_close), rtol=0, atol=0.01))


def verify_margin_balance(query_date: pd.Timestamp, observed_balance: float) -> bool:
    try:
        row = fetch_margin_for_date(query_date)
    except Exception as exc:  # noqa: BLE001
        print(f"Warning: unable to verify margin balance for {query_date.date()}: {exc}", flush=True)
        return False
    return bool(np.isclose(float(row["margin_balance_thousand_ntd"]), float(observed_balance), rtol=0, atol=0.5))


def build_data_quality_report(
    index_df: pd.DataFrame,
    margin_df: pd.DataFrame,
    model_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    diagnostic = diagnostic_source_frame(index_df, margin_df, model_df)
    reasons: dict[pd.Timestamp, list[str]] = {}

    add_diagnostic_reason(reasons, diagnostic, diagnostic["taiex_close"] <= 0, "taiex_close_lte_0")
    add_diagnostic_reason(reasons, diagnostic, diagnostic["margin_balance"] <= 0, "margin_balance_lte_0")

    duplicated_dates = pd.concat(
        [
            pd.to_datetime(index_df.loc[index_df["date"].duplicated(keep=False), "date"]),
            pd.to_datetime(margin_df.loc[margin_df["date"].duplicated(keep=False), "date"]),
            pd.to_datetime(model_df.loc[model_df["date"].duplicated(keep=False), "date"]),
        ],
        ignore_index=True,
    ).drop_duplicates()
    for item in duplicated_dates:
        reasons.setdefault(item.normalize(), []).append("date_duplicated")

    merge_nan = diagnostic["taiex_close"].isna() | diagnostic["margin_balance"].isna()
    add_diagnostic_reason(reasons, diagnostic, merge_nan, "required_field_nan_after_merge")

    taiex_jump = diagnostic["taiex_close"].pct_change().abs() > 0.15
    add_diagnostic_reason(reasons, diagnostic, taiex_jump, "taiex_single_day_return_abs_gt_15pct")

    margin_jump = diagnostic["margin_balance"].pct_change().abs() > 0.20
    add_diagnostic_reason(reasons, diagnostic, margin_jump, "margin_balance_single_day_return_abs_gt_20pct")

    return reasons_to_report(diagnostic, reasons, DATA_QUALITY_COLUMNS), diagnostic


def build_market_extreme_report(model_df: pd.DataFrame, diagnostic: pd.DataFrame) -> pd.DataFrame:
    reasons: dict[pd.Timestamp, list[str]] = {}

    add_diagnostic_reason(reasons, diagnostic, diagnostic["index_yoy"] > 0.80, "raw_index_yoy_gt_80pct")
    add_diagnostic_reason(reasons, diagnostic, diagnostic["index_qoq"] > 0.40, "raw_index_qoq_gt_40pct")
    add_diagnostic_reason(reasons, diagnostic, diagnostic["margin_roc"] > 0.40, "raw_margin_roc_gt_40pct")
    add_diagnostic_reason(reasons, diagnostic, diagnostic["index_yoy_z"] > 2.0, "index_yoy_z_gt_2")
    add_diagnostic_reason(reasons, diagnostic, diagnostic["index_qoq_z"] > 2.0, "index_qoq_z_gt_2")
    add_diagnostic_reason(reasons, diagnostic, diagnostic["margin_roc_z"] > 2.0, "margin_roc_z_gt_2")
    add_diagnostic_reason(
        reasons,
        diagnostic,
        diagnostic["margin_roc_autocorr_percentile_full_sample"] > 0.90,
        "margin_roc_autocorr_full_sample_percentile_gt_90pct",
    )
    add_diagnostic_reason(
        reasons,
        diagnostic,
        diagnostic["margin_roc_autocorr_rank_252"] > 0.90,
        "margin_roc_autocorr_rank_252_gt_90pct",
    )
    add_diagnostic_reason(
        reasons,
        diagnostic,
        diagnostic["margin_roc_persistence_score"] > 0.70,
        "margin_roc_persistence_score_gt_70pct",
    )

    return reasons_to_report(diagnostic, reasons, MARKET_EXTREME_COLUMNS)


def build_outlier_context(
    quality_report: pd.DataFrame, diagnostic: pd.DataFrame, context_window: int = 5
) -> pd.DataFrame:
    if quality_report.empty:
        return pd.DataFrame(columns=OUTLIER_CONTEXT_COLUMNS)

    source = diagnostic.sort_values("date").reset_index(drop=True)
    rows: list[dict[str, Any]] = []
    for outlier_date in pd.to_datetime(quality_report["date"]).drop_duplicates().sort_values():
        positions = source.index[pd.to_datetime(source["date"]) == outlier_date]
        if len(positions) == 0:
            continue
        position = int(positions[0])
        context = source.loc[max(0, position - context_window) : position + context_window]
        for _, row in context.iterrows():
            rows.append(
                {
                    "outlier_date": outlier_date,
                    "context_date": row["date"],
                    "taiex_close": row.get("taiex_close", math.nan),
                    "margin_balance": row.get("margin_balance", math.nan),
                    "index_yoy": row.get("index_yoy", math.nan),
                    "index_qoq": row.get("index_qoq", math.nan),
                    "margin_roc": row.get("margin_roc", math.nan),
                }
            )
    return pd.DataFrame(rows, columns=OUTLIER_CONTEXT_COLUMNS)


def write_diagnostic_csv(df: pd.DataFrame, output_path: Path, date_columns: list[str]) -> None:
    output_df = df.copy()
    for column in date_columns:
        if column in output_df.columns:
            output_df[column] = pd.to_datetime(output_df[column]).dt.date
    output_df.to_csv(output_path, index=False, encoding="utf-8-sig")


def plot_raw_percent(df: pd.DataFrame, output_path: Path) -> None:
    plot_df = df.dropna(subset=["index_yoy", "index_qoq", "margin_roc"])
    yoy = plot_df["index_yoy"] * 100
    qoq = plot_df["index_qoq"] * 100
    margin_roc = plot_df["margin_roc"] * 100

    fig, ax = plt.subplots(figsize=(14, 7))
    ax.plot(plot_df["date"], yoy, color="#f2c94c", linewidth=1.7, label="Index YoY")
    ax.plot(plot_df["date"], qoq, color="#2f80ed", linewidth=1.4, label="Index QoQ")
    ax.plot(plot_df["date"], margin_roc, color="#8c8c8c", linewidth=1.2, label="Margin ROC")
    ax.axhline(0, color="#333333", linewidth=0.8, alpha=0.6)
    ax.set_title("TAIEX Growth and Margin Balance ROC (Raw Percent Diagnostics)")
    ax.set_ylabel("Percent")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(loc="upper left")
    ax.xaxis.set_major_locator(mdates.YearLocator(1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def plot_factor_chart_debug(df: pd.DataFrame, output_path: Path) -> None:
    plot_df = df.dropna(subset=["index_yoy_z", "index_qoq_z", "margin_roc_z"])
    fig, ax = plt.subplots(figsize=(14, 7))
    bar_height = plot_df["margin_roc_autocorr_plot"].fillna(0).clip(0, 1)
    ax.bar(
        plot_df["date"],
        bar_height,
        bottom=-3.5,
        width=3,
        color="#bdbdbd",
        alpha=0.45,
        label="Margin ROC autocorr rank 252",
        align="center",
    )
    ax.plot(plot_df["date"], plot_df["index_yoy_z"], color="#f2c94c", linewidth=1.7, label="Index YoY z")
    ax.plot(plot_df["date"], plot_df["index_qoq_z"], color="#2f80ed", linewidth=1.4, label="Index QoQ z")
    ax.plot(plot_df["date"], plot_df["margin_roc_z"], color="#6e6e6e", linewidth=1.2, label="Margin ROC z")
    ax.axhline(0, color="#333333", linewidth=0.8, alpha=0.75)
    ax.set_ylim(-3.5, 3.5)
    ax.set_title("TAIEX Growth / Margin ROC Standardized Factor Chart - Z SCORE VERSION")
    ax.set_ylabel("Standardized score")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(loc="upper left", ncols=2)
    ax.xaxis.set_major_locator(mdates.YearLocator(1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def plot_factor_chart_smooth(df: pd.DataFrame, output_path: Path) -> None:
    plot_columns = ["index_yoy_z_plot", "index_qoq_z_plot", "margin_roc_z_plot"]
    plot_df = df.dropna(subset=plot_columns)
    fig, ax = plt.subplots(figsize=(14, 7))
    bar_height = plot_df["margin_roc_autocorr_bar"].fillna(0).clip(-1, 1) * 0.25
    ax.bar(
        plot_df["date"],
        bar_height,
        width=1,
        color="#bdbdbd",
        alpha=0.25,
        label="Margin ROC autocorr rank 252",
        align="center",
        zorder=1,
    )
    ax.plot(
        plot_df["date"],
        plot_df["index_yoy_z_plot"],
        color="#f2c94c",
        linewidth=1.2,
        label="Index YoY z smoothed",
        zorder=3,
    )
    ax.plot(
        plot_df["date"],
        plot_df["index_qoq_z_plot"],
        color="#2f80ed",
        linewidth=1.2,
        label="Index QoQ z smoothed",
        zorder=3,
    )
    ax.plot(
        plot_df["date"],
        plot_df["margin_roc_z_plot"],
        color="#6e6e6e",
        linewidth=1.2,
        label="Margin ROC z smoothed",
        zorder=3,
    )
    ax.axhline(0, color="#333333", linewidth=0.8, alpha=0.75, zorder=2)
    ax.set_ylim(-3.5, 3.5)
    ax.set_title("TAIEX Growth / Margin ROC Smoothed Standardized Factor Chart")
    ax.set_ylabel("Smoothed standardized score")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(loc="upper left")
    ax.xaxis.set_major_locator(mdates.YearLocator(1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def plot_reference_style_chart(df: pd.DataFrame, output_path: Path) -> None:
    plot_columns = ["index_yoy_ref", "index_qoq_ref", "margin_roc_ref"]
    plot_df = df.dropna(subset=plot_columns)
    fig, ax = plt.subplots(figsize=(16, 8))
    bar_base = -2.8
    bar_height = plot_df["autocorr_bar"].fillna(0).clip(-1, 1) * 0.25
    ax.bar(
        plot_df["date"],
        bar_height,
        bottom=bar_base,
        width=1,
        alpha=0.25,
        color="gray",
        label="Margin autocorr / persistence",
        align="center",
        zorder=1,
    )
    ax.plot(
        plot_df["date"],
        plot_df["index_yoy_ref"],
        color="#f2c94c",
        linewidth=1.2,
        label="Index YoY",
        zorder=3,
    )
    ax.plot(
        plot_df["date"],
        plot_df["index_qoq_ref"],
        color="#2f80ed",
        linewidth=1.2,
        label="Index QoQ",
        zorder=3,
    )
    ax.plot(
        plot_df["date"],
        plot_df["margin_roc_ref"],
        color="#6e6e6e",
        linewidth=1.2,
        label="Margin ROC",
        zorder=3,
    )
    ax.axhline(0, color="#333333", linewidth=0.8, alpha=0.75, zorder=2)
    ax.set_ylim(-3.2, 3.2)
    ax.set_title("TAIEX Growth / Margin ROC Reference Style Factor Chart")
    ax.set_ylabel("Relative factor score")
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
        "PRICE_AND_MARGIN_EXTREME": "#9467bd",
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


def write_summary(
    df: pd.DataFrame,
    config: ModelConfig,
    output_path: Path,
    quality_report: pd.DataFrame,
    market_extreme_report: pd.DataFrame,
) -> None:
    latest = df.dropna(subset=["index_close", "margin_balance_thousand_ntd"]).iloc[-1]
    latest_date = latest["date"].normalize()
    if quality_report.empty:
        data_quality_warning = False
    else:
        warning_dates = set(pd.to_datetime(quality_report["date"]).dt.normalize())
        data_quality_warning = latest_date in warning_dates
    market_extreme_warning = bool(
        (latest["index_yoy_z"] > 2.0)
        or (latest["index_qoq_z"] > 2.0)
        or (latest["margin_roc_z"] > 2.0)
        or (latest["margin_roc_autocorr_percentile_full_sample"] > 0.90)
        or (latest["margin_roc_autocorr_rank_252"] > 0.90)
        or (latest["margin_roc_persistence_score"] > 0.70)
    )
    latest_signal = derive_latest_signal(latest)
    raw_signal = str(latest.get("raw_signal", latest.get("signal", "NORMAL")))
    final_signal = str(latest.get("final_signal", latest_signal))
    final_signal_reason = str(latest.get("final_signal_reason", "not_available"))
    leverage_cycle_phase = str(latest.get("leverage_cycle_phase", leverage_cycle_phase_from_signal(final_signal)))
    transition_watch = str(latest.get("transition_watch", "none"))
    raw_signal_counts = df.get("raw_signal", df["signal"]).value_counts(dropna=False).to_dict()
    final_signal_counts = df.get("final_signal", df["signal"]).value_counts(dropna=False).to_dict()
    signal_counts = final_signal_counts
    summary = {
        "generated_at": datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
        "data_start": df["date"].min().date().isoformat(),
        "data_end": df["date"].max().date().isoformat(),
        "rows": int(len(df)),
        "data_quality_warning": data_quality_warning,
        "market_extreme_warning": market_extreme_warning,
        "latest_signal": latest_signal,
        "raw_signal": raw_signal,
        "final_signal": final_signal,
        "final_signal_reason": final_signal_reason,
        "leverage_cycle_phase": leverage_cycle_phase,
        "transition_watch": transition_watch,
        "latest_index_yoy": latest["index_yoy"],
        "latest_index_qoq": latest["index_qoq"],
        "latest_margin_roc": latest["margin_roc"],
        "latest_index_yoy_z": latest["index_yoy_z"],
        "latest_index_qoq_z": latest["index_qoq_z"],
        "latest_margin_roc_z": latest["margin_roc_z"],
        "latest_margin_roc_autocorr": latest["margin_roc_autocorr"],
        "latest_margin_roc_autocorr_percentile_full_sample": latest[
            "margin_roc_autocorr_percentile_full_sample"
        ],
        "latest_margin_roc_autocorr_rank_252": latest["margin_roc_autocorr_rank_252"],
        "latest_margin_roc_persistence_score": latest["margin_roc_persistence_score"],
        "latest_margin_roc_autocorr_percentile": latest["margin_roc_autocorr_percentile"],
        "autocorr_high_threshold": latest["autocorr_high_threshold"],
        "latest_close": latest["index_close"],
        "latest_margin_balance": latest["margin_balance_thousand_ntd"],
        "latest": {
            "date": latest["date"].date().isoformat(),
            "signal": final_signal,
            "raw_signal": raw_signal,
            "final_signal": final_signal,
            "final_signal_reason": final_signal_reason,
            "leverage_cycle_phase": leverage_cycle_phase,
            "transition_watch": transition_watch,
            "index_close": latest["index_close"],
            "index_yoy": latest["index_yoy"],
            "index_qoq": latest["index_qoq"],
            "margin_balance_thousand_ntd": latest["margin_balance_thousand_ntd"],
            "margin_roc": latest["margin_roc"],
            "index_yoy_z": latest["index_yoy_z"],
            "index_qoq_z": latest["index_qoq_z"],
            "margin_roc_z": latest["margin_roc_z"],
            "margin_roc_autocorr": latest["margin_roc_autocorr"],
            "margin_roc_autocorr_percentile_full_sample": latest[
                "margin_roc_autocorr_percentile_full_sample"
            ],
            "margin_roc_autocorr_rank_252": latest["margin_roc_autocorr_rank_252"],
            "margin_roc_persistence_score": latest["margin_roc_persistence_score"],
            "margin_roc_autocorr_percentile": latest["margin_roc_autocorr_percentile"],
            "autocorr_high_threshold": latest["autocorr_high_threshold"],
        },
        "signal_counts": signal_counts,
        "raw_signal_counts": raw_signal_counts,
        "final_signal_counts": final_signal_counts,
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


def write_outputs(
    df: pd.DataFrame,
    index_df: pd.DataFrame,
    margin_df: pd.DataFrame,
    config: ModelConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = config.output_dir / "tw_margin_autocorr_model.csv"
    factor_chart_path = config.output_dir / "tw_margin_autocorr_factor_chart.png"
    reference_style_path = config.output_dir / "tw_margin_autocorr_reference_style.png"
    factor_chart_smooth_path = config.output_dir / "tw_margin_autocorr_factor_chart_smooth.png"
    factor_chart_debug_path = config.output_dir / "tw_margin_autocorr_factor_chart_debug_v2.png"
    raw_percent_path = config.output_dir / "tw_margin_autocorr_raw_percent_debug.png"
    legacy_raw_percent_path = config.output_dir / "tw_margin_autocorr_raw_percent.png"
    legacy_growth_path = config.output_dir / "tw_margin_autocorr_growth.png"
    legacy_winsorized_path = config.output_dir / "tw_margin_autocorr_growth_winsorized.png"
    signal_path = config.output_dir / "tw_margin_autocorr_signal.png"
    quality_report_path = config.output_dir / "data_quality_report.csv"
    market_extreme_report_path = config.output_dir / "market_extreme_report.csv"
    outlier_context_path = config.output_dir / "outlier_context.csv"
    summary_path = config.output_dir / "signal_summary.json"

    quality_report, diagnostic = build_data_quality_report(index_df, margin_df, df)
    market_extreme_report = build_market_extreme_report(df, diagnostic)
    combined_report = pd.concat(
        [
            quality_report[["date"]].assign(reason_type="data_quality_error"),
            market_extreme_report[["date"]].assign(reason_type="market_extreme_warning"),
        ],
        ignore_index=True,
    )
    outlier_context = build_outlier_context(combined_report, diagnostic)

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    plot_reference_style_chart(df, factor_chart_path)
    plot_reference_style_chart(df, reference_style_path)
    plot_factor_chart_smooth(df, factor_chart_smooth_path)
    plot_factor_chart_debug(df, factor_chart_debug_path)
    plot_raw_percent(df, raw_percent_path)
    plot_signals(df, signal_path)
    write_diagnostic_csv(quality_report, quality_report_path, ["date"])
    write_diagnostic_csv(market_extreme_report, market_extreme_report_path, ["date"])
    write_diagnostic_csv(outlier_context, outlier_context_path, ["outlier_date", "context_date"])
    write_summary(df, config, summary_path, quality_report, market_extreme_report)

    print(f"Wrote {csv_path}", flush=True)
    for legacy_path in [legacy_growth_path, legacy_winsorized_path, legacy_raw_percent_path]:
        if legacy_path.exists():
            legacy_path.unlink()

    print(f"Wrote {factor_chart_path}", flush=True)
    print(f"Wrote {reference_style_path}", flush=True)
    print(f"Wrote {factor_chart_smooth_path}", flush=True)
    print(f"Wrote {factor_chart_debug_path}", flush=True)
    print(f"Wrote {raw_percent_path}", flush=True)
    print(f"Wrote {signal_path}", flush=True)
    print(f"Wrote {quality_report_path}", flush=True)
    print(f"Wrote {market_extreme_report_path}", flush=True)
    print(f"Wrote {outlier_context_path}", flush=True)
    print(f"Wrote {summary_path}", flush=True)
    return quality_report, outlier_context


def main() -> None:
    config = parse_args()
    output_csv = config.output_dir / "tw_margin_autocorr_model.csv"
    print(f"Fetching TAIEX index data from {config.start} to {config.end}...", flush=True)
    index_df = fetch_index_history(config.start, config.end, config.max_workers)
    print(f"Fetched {len(index_df)} index observations.", flush=True)
    margin_df = fetch_margin_history(index_df["date"], config, output_csv)
    print(f"Available margin observations: {len(margin_df)}", flush=True)
    model_df = build_model_frame(index_df, margin_df, config)
    quality_report, _ = write_outputs(model_df, index_df, margin_df, config)
    print(f"Data quality outliers: {len(quality_report)}", flush=True)


if __name__ == "__main__":
    main()
