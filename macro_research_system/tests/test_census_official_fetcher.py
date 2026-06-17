from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pandas as pd
import pytest
import yaml

from src.systems.common.fetchers.census_official_fetcher import (
    CensusConfigurationError,
    fetch_census_series,
    fetch_census_series_batch,
    normalize_census_observations,
)


class MockResponse:
    def __init__(self, payload: Any) -> None:
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
        assert "key" in query
        return MockResponse(
            [
                ["time", "cell_value", "NAME"],
                ["2026-04", "1420", "United States"],
                ["2026-05", ".", "United States"],
                ["2026-06", "not_available", "United States"],
            ]
        )


def test_fetch_census_series_uses_mocked_session_and_returns_normalized_frame(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CENSUS_API_KEY", "census-dummy-value")
    session = MockSession()

    result = fetch_census_series(
        "housing_starts_total",
        start_date="2026-01",
        end_date="2026-06",
        session=session,
        repo_root=tmp_path,
        dataset="timeseries/eits/resconst",
        variables=["time", "cell_value", "NAME"],
        geography="us:*",
    )

    assert len(session.urls) == 1
    assert isinstance(result, pd.DataFrame)
    assert result.loc[0, "series_id"] == "housing_starts_total"
    assert result.loc[0, "source_name"] == "Census"
    assert result.loc[0, "source_type"] == "official_public_real_economy"
    assert result.loc[0, "value"] == pytest.approx(1420)
    assert pd.isna(result.loc[1, "value"])
    assert pd.isna(result.loc[2, "value"])
    assert "census-dummy-value" not in result.to_string()


def test_fetch_census_series_batch_combines_mocked_series(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CENSUS_API_KEY", "census-dummy-value")
    session = MockSession()

    result = fetch_census_series_batch(
        ["housing_starts_total", "building_permits_total"],
        session=session,
        repo_root=tmp_path,
        dataset="timeseries/eits/resconst",
        variables=["time", "cell_value", "NAME"],
        geography="us:*",
    )

    assert set(result["series_id"]) == {"housing_starts_total", "building_permits_total"}
    assert len(session.urls) == 2
    assert result["source_name"].eq("Census").all()


def test_missing_census_api_key_raises_safe_error(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("CENSUS_API_KEY", raising=False)

    with pytest.raises(CensusConfigurationError) as excinfo:
        fetch_census_series("housing_starts_total", session=MockSession(), repo_root=tmp_path)

    message = str(excinfo.value)
    assert "CENSUS_API_KEY" in message
    assert "census-dummy-value" not in message


def test_normalize_census_observations_converts_dates_and_has_no_scores() -> None:
    result = normalize_census_observations(
        "housing_starts_total",
        [
            {"time": "2026-04", "cell_value": "1420"},
            {"year": "2026", "month": "05", "value": "1435"},
            {"date": "2026-06-01", "value": "(X)"},
        ],
        {
            "series_name": "Housing Starts Total",
            "frequency": "monthly",
            "unit": "thousands of units",
            "seasonal_adjustment": "seasonally adjusted annual rate",
        },
    )

    assert result.loc[0, "date"] == pd.Timestamp("2026-04-01")
    assert result.loc[1, "date"] == pd.Timestamp("2026-05-01")
    assert result.loc[2, "date"] == pd.Timestamp("2026-06-01")
    assert result.loc[0, "source_name"] == "Census"
    assert result.loc[0, "source_type"] == "official_public_real_economy"
    assert pd.isna(result.loc[2, "value"])
    assert "production_score" not in result.columns
    assert "composite_score" not in result.columns


def test_fetcher_does_not_write_files_or_use_census_as_cme_curve_source(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CENSUS_API_KEY", "census-dummy-value")

    result = fetch_census_series(
        "housing_starts_total",
        session=MockSession(),
        repo_root=tmp_path,
        dataset="timeseries/eits/resconst",
        variables=["time", "cell_value", "NAME"],
        geography="us:*",
    )

    assert list(tmp_path.iterdir()) == []
    assert "CME" not in result.to_string()
    assert "CL" not in result.to_string()


def test_census_config_todo_verify_entries_are_inactive() -> None:
    config_path = Path("macro_research_system/config/census_official_series.yaml")
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    active_groups = {key: value for key, value in payload.items() if key != "todo_verify"}

    active_todo = [
        entry
        for entries in active_groups.values()
        for entry in entries
        if entry.get("series_id") == "TODO_VERIFY" or entry.get("active") is False
    ]
    todo_entries = [
        entry
        for entries in payload.get("todo_verify", {}).values()
        for entry in entries.values()
    ]

    assert active_todo == []
    assert todo_entries
    assert all(entry["active"] is False for entry in todo_entries)
    assert all(entry["status"] == "TODO_VERIFY" for entry in todo_entries)
