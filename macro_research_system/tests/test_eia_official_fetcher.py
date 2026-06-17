from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pandas as pd
import pytest
import yaml

from src.systems.common.fetchers.eia_official_fetcher import (
    EIAConfigurationError,
    fetch_eia_series,
    fetch_eia_series_batch,
    normalize_eia_observations,
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
        series_id = request.full_url.split("/seriesid/", 1)[1].split("?", 1)[0]
        query = parse_qs(urlparse(request.full_url).query)
        assert "api_key" in query
        return MockResponse(
            {
                "response": {
                    "data": [
                        {"period": "2026-06-05", "value": "432100", "units": "MBBL"},
                        {"period": "2026-06-12", "value": "."},
                        {"period": "2026-06-19", "value": "not_available"},
                    ]
                },
                "series_id": series_id,
                "series_name": f"{series_id} mock title",
                "frequency": "weekly",
                "unit": "MBBL",
            }
        )


def test_fetch_eia_series_uses_mocked_session_and_returns_normalized_frame(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EIA_API_KEY", "eia-dummy-value")
    session = MockSession()

    result = fetch_eia_series(
        "PET.WCESTUS1.W",
        start_date="2026-01-01",
        end_date="2026-06-30",
        session=session,
        repo_root=tmp_path,
    )

    assert len(session.urls) == 1
    assert isinstance(result, pd.DataFrame)
    assert result.loc[0, "series_id"] == "PET.WCESTUS1.W"
    assert result.loc[0, "series_name"] == "PET.WCESTUS1.W mock title"
    assert result.loc[0, "source_name"] == "EIA"
    assert result.loc[0, "source_type"] == "official_public_energy"
    assert result.loc[0, "value"] == pytest.approx(432100)
    assert pd.isna(result.loc[1, "value"])
    assert pd.isna(result.loc[2, "value"])
    assert "eia-dummy-value" not in result.to_string()


def test_fetch_eia_series_batch_combines_mocked_series(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EIA_API_KEY", "eia-dummy-value")
    session = MockSession()

    result = fetch_eia_series_batch(["PET.WCESTUS1.W", "PET.WGTSTUS1.W"], session=session, repo_root=tmp_path)

    assert set(result["series_id"]) == {"PET.WCESTUS1.W", "PET.WGTSTUS1.W"}
    assert len(session.urls) == 2
    assert result["source_name"].eq("EIA").all()


def test_missing_eia_api_key_raises_safe_error(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("EIA_API_KEY", raising=False)

    with pytest.raises(EIAConfigurationError) as excinfo:
        fetch_eia_series("PET.WCESTUS1.W", session=MockSession(), repo_root=tmp_path)

    message = str(excinfo.value)
    assert "EIA_API_KEY" in message
    assert "eia-dummy-value" not in message


def test_normalize_eia_observations_converts_dates_and_has_no_scores() -> None:
    result = normalize_eia_observations(
        "PET.WCESTUS1.W",
        [
            {"period": "2026-06-05", "value": "432100", "units": "MBBL"},
            {"period": "2026-06", "value": "431000"},
            {"date": "2026-06-19", "value": "-"},
        ],
        {
            "series_name": "U.S. Ending Stocks of Crude Oil",
            "frequency": "weekly",
            "unit": "MBBL",
        },
    )

    assert result.loc[0, "date"] == pd.Timestamp("2026-06-05")
    assert result.loc[1, "date"] == pd.Timestamp("2026-06-01")
    assert result.loc[0, "source_name"] == "EIA"
    assert result.loc[0, "source_type"] == "official_public_energy"
    assert pd.isna(result.loc[2, "value"])
    assert "production_score" not in result.columns
    assert "composite_score" not in result.columns


def test_fetcher_does_not_write_files_or_use_eia_as_cme_curve_source(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EIA_API_KEY", "eia-dummy-value")

    result = fetch_eia_series("PET.WCESTUS1.W", session=MockSession(), repo_root=tmp_path)

    assert list(tmp_path.iterdir()) == []
    assert "CME" not in result.to_string()
    assert "CL" not in result.to_string()


def test_eia_config_todo_verify_entries_are_inactive() -> None:
    config_path = Path("macro_research_system/config/eia_official_series.yaml")
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
