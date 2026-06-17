from __future__ import annotations

import pandas as pd
import pytest

from src.systems.common.macro_series_schema import (
    REQUIRED_MACRO_SERIES_COLUMNS,
    normalize_observation_records,
    validate_macro_series_frame,
)


def test_validate_macro_series_frame_accepts_required_columns_and_normalizes_types() -> None:
    frame = pd.DataFrame(
        [
            {
                "date": "2026-06-12",
                "series_id": "DGS10",
                "series_name": "10-Year Treasury Constant Maturity Rate",
                "value": "4.25",
                "source_name": "FRED",
                "source_type": "official_public_macro",
                "frequency": "daily",
                "unit": "percent",
                "seasonal_adjustment": "not seasonally adjusted",
                "fetched_at": "2026-06-17T00:00:00+00:00",
            }
        ]
    )

    result = validate_macro_series_frame(frame)

    assert list(result.columns[: len(REQUIRED_MACRO_SERIES_COLUMNS)]) == REQUIRED_MACRO_SERIES_COLUMNS
    assert pd.api.types.is_datetime64_any_dtype(result["date"])
    assert result.loc[0, "value"] == pytest.approx(4.25)
    assert result.loc[0, "source_name"] == "FRED"
    assert result.loc[0, "source_type"] == "official_public_macro"


def test_validate_macro_series_frame_rejects_missing_required_columns() -> None:
    frame = pd.DataFrame({"date": ["2026-06-12"], "value": [4.25]})

    with pytest.raises(ValueError, match="missing required"):
        validate_macro_series_frame(frame)


def test_normalize_observation_records_preserves_metadata_and_optional_columns() -> None:
    records = [
        {
            "date": "2026-06-12",
            "value": "4.25",
            "realtime_start": "2026-06-13",
            "realtime_end": "2026-06-14",
            "observation_status": "final",
            "notes": "mock observation",
        },
        {"date": "2026-06-13", "value": "."},
    ]
    metadata = {
        "series_id": "DGS10",
        "series_name": "10-Year Treasury Constant Maturity Rate",
        "source_name": "FRED",
        "source_type": "official_public_macro",
        "frequency": "daily",
        "unit": "percent",
        "seasonal_adjustment": "not seasonally adjusted",
        "fetched_at": "2026-06-17T00:00:00+00:00",
    }

    result = normalize_observation_records(records, metadata)

    assert list(result["series_id"]) == ["DGS10", "DGS10"]
    assert pd.isna(result.loc[1, "value"])
    assert result.loc[0, "realtime_start"] == "2026-06-13"
    assert result.loc[0, "notes"] == "mock observation"
    assert set(REQUIRED_MACRO_SERIES_COLUMNS).issubset(result.columns)


def test_normalize_observation_records_rejects_missing_metadata() -> None:
    with pytest.raises(ValueError, match="metadata"):
        normalize_observation_records([{"date": "2026-06-12", "value": "4.25"}], {"series_id": "DGS10"})
