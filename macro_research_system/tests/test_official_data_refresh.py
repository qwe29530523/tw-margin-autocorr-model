from __future__ import annotations

from pathlib import Path

import pytest

from src.systems.common.runners.official_data_refresh import (
    build_official_source_diagnostics,
    build_refresh_plan,
    run_official_data_refresh_dry_run,
    summarize_refresh_diagnostics,
)


CONFIGURED_ENV = {
    "FRED_API_KEY": "fred-dummy-value",
    "BLS_API_KEY": "bls-dummy-value",
    "EIA_API_KEY": "eia-dummy-value",
    "CENSUS_API_KEY": "census-dummy-value",
    "METALPRICE_API_KEY": "metalprice-dummy-value",
}


@pytest.fixture(autouse=True)
def configured_env(monkeypatch) -> None:
    for key, value in CONFIGURED_ENV.items():
        monkeypatch.setenv(key, value)


def _by_source(rows: list[dict]) -> dict[str, dict]:
    return {row["source_name"]: row for row in rows}


def test_diagnostics_include_registered_sources_and_safe_metadata() -> None:
    diagnostics = build_official_source_diagnostics()
    by_source = _by_source(diagnostics)

    assert {"FRED", "BLS", "EIA", "Census", "MetalPriceAPI", "CME DataMine"}.issubset(by_source)
    assert by_source["FRED"]["is_configured"] is True
    assert by_source["BLS"]["is_configured"] is True
    assert by_source["EIA"]["is_configured"] is True
    assert by_source["Census"]["is_configured"] is True
    assert by_source["Census"]["source_type"] == "official_public_real_economy"
    assert by_source["Census"]["active_series_count"] == 0
    assert by_source["Census"]["todo_verify_count"] == 11
    assert by_source["Census"]["planned_for_refresh"] is False
    assert by_source["Census"]["excluded_reason"] == "NO_ACTIVE_SERIES"
    assert by_source["CME DataMine"]["blocker_status"] == "open"
    assert by_source["CME DataMine"]["planned_for_refresh"] is False
    assert by_source["CME DataMine"]["excluded_reason"] == "BLOCKER_OPEN"
    assert by_source["MetalPriceAPI"]["research_only"] is True
    assert by_source["MetalPriceAPI"]["planned_for_refresh"] is False
    assert by_source["MetalPriceAPI"]["excluded_reason"] == "RESEARCH_ONLY_EXCLUDED"
    assert "fred-dummy-value" not in str(diagnostics)
    assert "census-dummy-value" not in str(diagnostics)


def test_official_refresh_plan_includes_only_configured_active_official_series() -> None:
    plan = build_refresh_plan()
    sources = {row["source_name"] for row in plan}

    assert {"FRED", "BLS", "EIA"}.issubset(sources)
    assert "Census" not in sources
    assert "CME DataMine" not in sources
    assert "MetalPriceAPI" not in sources
    assert all(row["active"] is True for row in plan)
    assert all(row["refresh_mode"] == "dry_run" for row in plan)
    assert all(row["series_id"] != "TODO_VERIFY" for row in plan)
    assert all("production_score" not in row for row in plan)
    assert all("composite_score" not in row for row in plan)


def test_metalpriceapi_is_included_only_when_research_only_is_requested() -> None:
    default_plan = build_refresh_plan()
    research_plan = build_refresh_plan(include_research_only=True)

    assert "MetalPriceAPI" not in {row["source_name"] for row in default_plan}
    metal_rows = [row for row in research_plan if row["source_name"] == "MetalPriceAPI"]
    assert {row["series_id"] for row in metal_rows} == {"WTI", "BRENT", "NATURALGAS", "GASOLINE"}
    assert all(row["research_only"] is True for row in metal_rows)
    assert all("CL individual contract-month settlement" in row["not_usable_for"] for row in metal_rows)


def test_dry_run_does_not_write_files_or_call_network(tmp_path: Path) -> None:
    before = set(tmp_path.iterdir())

    result = run_official_data_refresh_dry_run(include_research_only=True)

    assert set(tmp_path.iterdir()) == before
    assert result["mode"] == "dry_run"
    assert result["network_calls"] == 0
    assert result["files_written"] == 0
    assert result["refresh_plan"]
    assert "fred-dummy-value" not in str(result)
    assert "metalprice-dummy-value" not in str(result)
    assert "production_score" not in result
    assert "composite_score" not in result


def test_summary_preserves_wti_blocker_and_counts() -> None:
    diagnostics = build_official_source_diagnostics()
    summary = summarize_refresh_diagnostics(diagnostics)

    assert summary["source_count"] >= 6
    assert summary["official_planned_source_count"] == 3
    assert summary["research_only_source_count"] == 1
    assert summary["blocked_source_count"] == 1
    assert summary["wti_m1_m2_m3_blocker_status"] == "open"
    assert summary["census_active_series_count"] == 0
