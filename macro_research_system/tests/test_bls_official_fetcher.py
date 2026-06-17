from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from src.systems.common.fetchers.bls_official_fetcher import (
    BLSConfigurationError,
    fetch_bls_series,
    fetch_bls_series_batch,
    normalize_bls_observations,
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
        self.requests: list[Any] = []

    def urlopen(self, request, timeout: int = 20) -> MockResponse:
        self.requests.append(request)
        payload = json.loads(request.data.decode("utf-8"))
        series_ids = payload["seriesid"]
        return MockResponse(
            {
                "status": "REQUEST_SUCCEEDED",
                "Results": {
                    "series": [
                        {
                            "seriesID": series_id,
                            "data": [
                                {"year": "2026", "period": "M02", "periodName": "February", "value": "310.2"},
                                {"year": "2026", "period": "M03", "periodName": "March", "value": "."},
                                {"year": "2026", "period": "M04", "periodName": "April", "value": "not_available"},
                            ],
                        }
                        for series_id in series_ids
                    ]
                },
            }
        )


def test_fetch_bls_series_uses_mocked_session_and_returns_normalized_frame(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BLS_API_KEY", "bls-dummy-value")
    session = MockSession()

    result = fetch_bls_series(
        "CUUR0000SA0",
        start_year=2025,
        end_year=2026,
        session=session,
        repo_root=tmp_path,
    )

    assert len(session.requests) == 1
    assert isinstance(result, pd.DataFrame)
    assert result.loc[0, "series_id"] == "CUUR0000SA0"
    assert result.loc[0, "series_name"] == "CUUR0000SA0"
    assert result.loc[0, "source_name"] == "BLS"
    assert result.loc[0, "source_type"] == "official_public_labor_inflation"
    assert result.loc[0, "value"] == pytest.approx(310.2)
    assert pd.isna(result.loc[1, "value"])
    assert pd.isna(result.loc[2, "value"])
    assert "bls-dummy-value" not in result.to_string()


def test_fetch_bls_series_batch_combines_mocked_series(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BLS_API_KEY", "bls-dummy-value")
    session = MockSession()

    result = fetch_bls_series_batch(["CUUR0000SA0", "CUUR0000SAH1"], session=session, repo_root=tmp_path)

    assert set(result["series_id"]) == {"CUUR0000SA0", "CUUR0000SAH1"}
    assert len(session.requests) == 1
    assert result["source_name"].eq("BLS").all()


def test_missing_bls_api_key_raises_safe_error(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("BLS_API_KEY", raising=False)

    with pytest.raises(BLSConfigurationError) as excinfo:
        fetch_bls_series("CUUR0000SA0", session=MockSession(), repo_root=tmp_path)

    message = str(excinfo.value)
    assert "BLS_API_KEY" in message
    assert "bls-dummy-value" not in message


def test_normalize_bls_observations_converts_periods_and_has_no_scores() -> None:
    result = normalize_bls_observations(
        "CUUR0000SA0",
        [
            {"year": "2026", "period": "M02", "periodName": "February", "value": "310.2"},
            {"year": "2026", "period": "Q02", "periodName": "2nd Quarter", "value": "311.0"},
            {"year": "2026", "period": "M13", "periodName": "Annual", "value": "309.5"},
        ],
        {
            "series_name": "CPI All Urban Consumers",
            "frequency": "monthly",
            "unit": "index",
            "seasonal_adjustment": "not seasonally adjusted",
        },
    )

    assert result.loc[0, "date"] == pd.Timestamp("2026-02-01")
    assert result.loc[1, "date"] == pd.Timestamp("2026-04-01")
    assert result.loc[2, "date"] == pd.Timestamp("2026-01-01")
    assert result.loc[0, "source_name"] == "BLS"
    assert result.loc[0, "source_type"] == "official_public_labor_inflation"
    assert "production_score" not in result.columns
    assert "composite_score" not in result.columns


def test_fetcher_does_not_write_files_or_use_bls_as_cme_curve_source(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BLS_API_KEY", "bls-dummy-value")
    session = MockSession()

    result = fetch_bls_series("CUUR0000SA0", session=session, repo_root=tmp_path)

    assert list(tmp_path.iterdir()) == []
    assert "CME" not in result.to_string()
    assert "CL" not in result.to_string()
