from __future__ import annotations

import argparse

import pandas as pd
from pandas.errors import EmptyDataError

from src.fetchers.eia_fetcher import fetch_many_eia_series
from src.fetchers.fred_fetcher import fetch_many_fred_series
from src.fetchers.yahoo_fetcher import fetch_yahoo_prices
from src.processors.macro_regime_engine import build_macro_summary
from src.processors.oil_engine import build_oil_frame
from src.processors.rates_curve_engine import build_rates_curve_frame
from src.reports.markdown_report import write_markdown_report
from src.settings import load_settings
from src.utils.io import ensure_dirs, latest_file, read_frame, save_processed_frame, save_raw_frame
from src.utils.logging import get_logger


logger = get_logger(__name__)


def fetch() -> None:
    settings = load_settings()
    ensure_dirs(settings.raw_dir, settings.processed_dir, settings.reports_dir)
    fred = fetch_many_fred_series(api_key=settings.fred_api_key)
    eia = fetch_many_eia_series(api_key=settings.eia_api_key)
    save_raw_frame(fred, settings.raw_dir, "fred")
    save_raw_frame(eia, settings.raw_dir, "eia")
    if settings.use_yahoo:
        yahoo = fetch_yahoo_prices()
        save_raw_frame(yahoo, settings.raw_dir, "yahoo")
    else:
        logger.info("Yahoo overlay is OFF; skipping Yahoo fetch.")


def process() -> None:
    settings = load_settings()
    ensure_dirs(settings.processed_dir)
    fred = read_frame(latest_file(settings.raw_dir, "fred_*.csv"))
    eia = read_frame(latest_file(settings.raw_dir, "eia_*.csv"))
    oil = build_oil_frame(fred, eia)
    rates = build_rates_curve_frame(fred)

    save_processed_frame(oil, settings.processed_dir, "oil_engine")
    save_processed_frame(rates, settings.processed_dir, "rates_curve")


def report() -> None:
    settings = load_settings()
    oil = read_processed(settings, "oil_engine")
    rates = read_processed(settings, "rates_curve")
    summary = build_macro_summary(oil, rates, yahoo_overlay=settings.use_yahoo)
    path = write_markdown_report(summary, settings.reports_dir)
    logger.info("Wrote report: %s", path)


def read_processed(settings, stem: str) -> pd.DataFrame:
    parquet = settings.processed_dir / f"{stem}.parquet"
    csv = settings.processed_dir / f"{stem}.csv"
    if parquet.exists():
        return pd.read_parquet(parquet)
    if csv.exists():
        try:
            return pd.read_csv(csv)
        except EmptyDataError:
            logger.warning("Processed file has no columns, treating as empty: %s", csv)
            return pd.DataFrame()
    return pd.DataFrame()


def all_steps() -> None:
    fetch()
    process()
    report()


def main() -> None:
    parser = argparse.ArgumentParser(description="Oil + rates macro monitor")
    parser.add_argument("command", choices=["fetch", "process", "report", "all"])
    args = parser.parse_args()
    commands = {
        "fetch": fetch,
        "process": process,
        "report": report,
        "all": all_steps,
    }
    commands[args.command]()


if __name__ == "__main__":
    main()
