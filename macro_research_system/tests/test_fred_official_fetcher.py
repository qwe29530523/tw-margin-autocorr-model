from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pandas as pd
import pytest

from src.systems.common.fetchers.fred_official_fetcher import (
    FREDConfigurationError,
    fetch_fred_series,
    fetch_fred_series_batch,
    normalize_fred_observations,
)


class MockResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self) -> "MockResponse":
        return self

    def __exit__(self, *args) -> None:
        return None


class MockSession:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def urlopen(self, request, timeout: int = 20) -> MockResponse:
        self.urls.append(request.full_url)
        query = parse_qs(urlparse(request.full_url).query)
        series_id = query["series_id"][0]
        return MockResponse(
            {
                "observations": [
                    {"date": "2026-06-12", "value": "4.25", "realtime_start": "2026-06-13"},
                    {"date": "2026-06-13", "value": "."},
                ],
                "series_metadata": {
                    "id": series_id,
                    "title": f"{series_id} mock title",
                    "frequency": "Daily",
                    "units": "Percent",
                    "seasonal_adjustment": "Not Seasonally Adjusted",
                },
            }
        )


def test_fetch_fred_series_uses_mocked_session_and_returns_normalized_frame(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FRED_API_KEY", "fred-dummy-value")
    session = MockSession()

    result = fetch_fred_series(
        "DGS10",
        start_date="2026-01-01",
        end_date="2026-06-30",
        session=session,
        repo_root=tmp_path,
    )

    assert len(session.urls) == 1
    assert isinstance(result, pd.DataFrame)
    assert result.loc[0, "series_id"] == "DGS10"
    assert result.loc[0, "series_name"] == "DGS10 mock title"
    assert result.loc[0, "source_name"] == "FRED"
    assert result.loc[0, "source_type"] == "official_public_macro"
    assert pd.isna(result.loc[1, "value"])
    assert "fred-dummy-value" not in result.to_string()


def test_fetch_fred_series_batch_combines_mocked_series(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FRED_API_KEY", "fred-dummy-value")
    session = MockSession()

    result = fetch_fred_series_batch(["DGS2", "DGS10"], session=session, repo_root=tmp_path)

    assert set(result["series_id"]) == {"DGS2", "DGS10"}
    assert len(session.urls) == 2
    assert result["source_name"].eq("FRED").all()


def test_missing_fred_api_key_raises_safe_error(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)

    with pytest.raises(FREDConfigurationError) as excinfo:
        fetch_fred_series("DGS10", session=MockSession(), repo_root=tmp_path)

    message = str(excinfo.value)
    assert "FRED_API_KEY" in message
    assert "fred-dummy-value" not in message


def test_normalize_fred_observations_has_required_schema_and_no_scores() -> None:
    result = normalize_fred_observations(
        "DGS10",
        [{"date": "2026-06-12", "value": "4.25"}, {"date": "2026-06-13", "value": "."}],
        {
            "title": "10-Year Treasury Constant Maturity Rate",
            "frequency": "Daily",
            "units": "Percent",
            "seasonal_adjustment": "Not Seasonally Adjusted",
        },
    )

    assert result.loc[0, "value"] == pytest.approx(4.25)
    assert pd.isna(result.loc[1, "value"])
    assert result.loc[0, "source_name"] == "FRED"
    assert result.loc[0, "source_type"] == "official_public_macro"
    assert "production_score" not in result.columns
    assert "composite_score" not in result.columns


def test_fetcher_does_not_write_files(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FRED_API_KEY", "fred-dummy-value")

    fetch_fred_series("DGS10", session=MockSession(), repo_root=tmp_path)

    assert list(tmp_path.iterdir()) == []
