from __future__ import annotations

from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError

from src.utils.dates import timestamp_for_filename
from src.utils.logging import get_logger


logger = get_logger(__name__)


def ensure_dirs(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def save_raw_frame(df: pd.DataFrame, output_dir: Path, stem: str) -> Path:
    ensure_dirs(output_dir)
    path = output_dir / f"{stem}_{timestamp_for_filename()}.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    logger.info("Wrote raw file: %s", path)
    return path


def save_processed_frame(df: pd.DataFrame, output_dir: Path, stem: str) -> Path:
    ensure_dirs(output_dir)
    parquet_path = output_dir / f"{stem}.parquet"
    try:
        df.to_parquet(parquet_path, index=False)
        logger.info("Wrote processed parquet: %s", parquet_path)
        return parquet_path
    except Exception as exc:  # noqa: BLE001
        csv_path = output_dir / f"{stem}.csv"
        logger.warning("Parquet unavailable for %s, falling back to CSV: %s", stem, exc)
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        logger.info("Wrote processed CSV: %s", csv_path)
        return csv_path


def read_frame(path: Path | None) -> pd.DataFrame:
    if path is None or not path.exists():
        return pd.DataFrame()
    try:
        if path.suffix.lower() == ".parquet":
            return pd.read_parquet(path)
        return pd.read_csv(path)
    except EmptyDataError:
        logger.warning("Input file has no columns, treating as empty: %s", path)
        return pd.DataFrame()


def latest_file(directory: Path, pattern: str) -> Path | None:
    matches = sorted(directory.glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)
    return matches[0] if matches else None
