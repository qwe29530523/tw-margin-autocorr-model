from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

import pandas as pd


REQUIRED_MACRO_SERIES_COLUMNS = [
    "date",
    "series_id",
    "series_name",
    "value",
    "source_name",
    "source_type",
    "frequency",
    "unit",
    "seasonal_adjustment",
    "fetched_at",
]

OPTIONAL_MACRO_SERIES_COLUMNS = [
    "realtime_start",
    "realtime_end",
    "observation_status",
    "notes",
]


def utc_fetched_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_macro_series_frame(df: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in REQUIRED_MACRO_SERIES_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Macro series frame missing required columns: {', '.join(missing)}")

    result = df.copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    result["value"] = pd.to_numeric(result["value"], errors="coerce")

    ordered_columns = [
        *REQUIRED_MACRO_SERIES_COLUMNS,
        *[column for column in OPTIONAL_MACRO_SERIES_COLUMNS if column in result.columns],
        *[
            column
            for column in result.columns
            if column not in REQUIRED_MACRO_SERIES_COLUMNS and column not in OPTIONAL_MACRO_SERIES_COLUMNS
        ],
    ]
    return result.loc[:, ordered_columns]


def normalize_observation_records(
    records: Iterable[dict[str, Any]],
    metadata: dict[str, Any],
) -> pd.DataFrame:
    required_metadata = [
        "series_id",
        "series_name",
        "source_name",
        "source_type",
        "frequency",
        "unit",
        "seasonal_adjustment",
        "fetched_at",
    ]
    missing_metadata = [key for key in required_metadata if key not in metadata]
    if missing_metadata:
        raise ValueError(f"Macro series metadata missing required fields: {', '.join(missing_metadata)}")

    rows: list[dict[str, Any]] = []
    for record in records:
        row = {
            "date": record.get("date"),
            "series_id": metadata["series_id"],
            "series_name": metadata["series_name"],
            "value": _coerce_observation_value(record.get("value")),
            "source_name": metadata["source_name"],
            "source_type": metadata["source_type"],
            "frequency": metadata["frequency"],
            "unit": metadata["unit"],
            "seasonal_adjustment": metadata["seasonal_adjustment"],
            "fetched_at": metadata["fetched_at"],
        }
        for column in OPTIONAL_MACRO_SERIES_COLUMNS:
            if column in record:
                row[column] = record.get(column)
        rows.append(row)

    columns = REQUIRED_MACRO_SERIES_COLUMNS + OPTIONAL_MACRO_SERIES_COLUMNS
    if not rows:
        return pd.DataFrame(columns=columns)
    return validate_macro_series_frame(pd.DataFrame(rows))


def _coerce_observation_value(value: Any) -> Any:
    if value in {None, ".", "", "NaN"}:
        return pd.NA
    return value
