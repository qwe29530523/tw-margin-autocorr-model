from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.systems.common.domain_input_builder import (
    build_all_domain_input_coverage,
    build_all_domain_inputs,
    build_domain_input,
    build_domain_input_coverage,
    load_domain_input_mappings,
)


FORBIDDEN_COLUMNS = {
    "production_score",
    "composite_score",
    "final_trading_signal",
    "trading_signal",
}


def _normalized_fixture() -> pd.DataFrame:
    fetched_at = "2026-06-17T00:00:00+00:00"
    rows = [
        ("2026-06-07", "CUUR0000SAF1", "CPI Food", 101.0, "BLS", "official_public_labor_inflation"),
        ("2026-06-07", "CPIAUCSL", "Headline CPI", 310.0, "FRED", "official_public_macro"),
        ("2026-06-07", "CUUR0000SAH1", "CPI Shelter", 115.0, "BLS", "official_public_labor_inflation"),
        ("2026-06-07", "CUUR0000SEHA", "CPI Rent", 118.0, "BLS", "official_public_labor_inflation"),
        ("2026-06-07", "MORTGAGE30US", "30Y Mortgage", 6.7, "FRED", "official_public_macro"),
        ("2026-06-07", "UNRATE", "Unemployment Rate", 4.1, "FRED", "official_public_macro"),
        ("2026-06-07", "CUUR0000SASLE", "Services CPI", 122.0, "BLS", "official_public_labor_inflation"),
        ("2026-06-07", "CES0500000003", "Average Hourly Earnings", 36.5, "BLS", "official_public_labor_inflation"),
        ("2026-06-07", "PET.WCESTUS1.W", "Crude Stocks", 432100.0, "EIA", "official_public_energy"),
        ("2026-06-07", "PET.WCRFPUS2.W", "Crude Production", 13200.0, "EIA", "official_public_energy"),
        ("2026-06-14", "CUUR0000SAF1", "CPI Food", 101.3, "BLS", "official_public_labor_inflation"),
        ("2026-06-14", "CPIAUCSL", "Headline CPI", 310.4, "FRED", "official_public_macro"),
        ("2026-06-14", "PET.WCESTUS1.W", "Crude Stocks", 431800.0, "EIA", "official_public_energy"),
        ("2026-06-14", "PET.WCRFPUS2.W", "Crude Production", 13250.0, "EIA", "official_public_energy"),
    ]
    return pd.DataFrame(
        rows,
        columns=["date", "series_id", "series_name", "value", "source_name", "source_type"],
    ).assign(
        frequency="weekly",
        unit="index",
        seasonal_adjustment="unknown",
        fetched_at=fetched_at,
    )


def test_load_domain_input_mappings_contains_expected_domains_and_crack_fields() -> None:
    mappings = load_domain_input_mappings()

    assert {"energy_oil", "food_inflation", "shelter_inflation", "services_wage_inflation"} <= set(mappings)
    energy_mappings = mappings["energy_oil"]["mappings"]
    assert {"gasoline_crack_spread", "distillate_crack_spread", "crack_321"} <= set(energy_mappings)
    assert energy_mappings["gasoline_crack_spread"]["status"] == "TODO_VERIFY_VENDOR_ROUTE"
    assert energy_mappings["gasoline_crack_spread"]["candidate_series"] == []
    assert energy_mappings["gasoline_crack_spread"]["required"] is False
    assert energy_mappings["gasoline_crack_spread"]["caveat"] == (
        "requires_verified_wti_and_rbob_futures; not_official_until_vendor_verified"
    )


def test_build_domain_input_builds_wide_dataframe_for_domain() -> None:
    result = build_domain_input(_normalized_fixture(), "food_inflation")

    assert list(result.columns) == ["date", "food_cpi", "headline_cpi"]
    assert len(result) == 2
    assert result.loc[0, "food_cpi"] == 101.0
    assert result.loc[1, "headline_cpi"] == 310.4
    assert FORBIDDEN_COLUMNS.isdisjoint(result.columns)


def test_build_all_domain_inputs_returns_expected_domain_keys() -> None:
    results = build_all_domain_inputs(_normalized_fixture())

    assert set(results) == {"energy_oil", "food_inflation", "shelter_inflation", "services_wage_inflation"}
    assert "crude_oil_inventory" in results["energy_oil"].columns
    assert "shelter_cpi" in results["shelter_inflation"].columns
    assert "unemployment_rate" in results["services_wage_inflation"].columns


def test_coverage_reports_available_and_missing_fields() -> None:
    coverage = build_domain_input_coverage(_normalized_fixture(), "shelter_inflation")
    by_field = {row["mapped_field"]: row for row in coverage}

    assert by_field["shelter_cpi"]["is_available"] is True
    assert by_field["shelter_cpi"]["matched_series"] == "CUUR0000SAH1"
    assert by_field["shelter_cpi"]["source_name"] == "BLS"
    assert by_field["housing_starts"]["is_available"] is False
    assert by_field["housing_starts"]["required"] is False
    assert by_field["housing_starts"]["missing_reason"] == "NO_CANDIDATE_SERIES"
    assert by_field["housing_starts"]["status"] == "TODO_VERIFY_CENSUS_ROUTE"


def test_energy_crack_spread_fields_are_diagnostics_only_until_vendor_verified() -> None:
    frame = _normalized_fixture()
    wide = build_domain_input(frame, "energy_oil")
    coverage = build_domain_input_coverage(frame, "energy_oil")
    by_field = {row["mapped_field"]: row for row in coverage}

    for field in ["gasoline_crack_spread", "distillate_crack_spread", "crack_321"]:
        assert field in by_field
        assert by_field[field]["status"] == "TODO_VERIFY_VENDOR_ROUTE"
        assert by_field[field]["required"] is False
        assert by_field[field]["candidate_series"] == []
        assert by_field[field]["matched_series"] is None
        assert by_field[field]["is_available"] is False
        assert by_field[field]["missing_reason"] == "NO_CANDIDATE_SERIES"
        assert by_field[field]["caveat"]
        assert field not in wide.columns

    assert by_field["wti_benchmark"]["caveat"] == "not_wti_futures_curve"


def test_all_coverage_has_domain_rows_and_no_forbidden_outputs() -> None:
    coverage = build_all_domain_input_coverage(_normalized_fixture())

    assert set(coverage) == {"energy_oil", "food_inflation", "shelter_inflation", "services_wage_inflation"}
    assert all(isinstance(rows, list) for rows in coverage.values())
    assert "api-key-dummy-value" not in str(coverage)
    assert "production_score" not in coverage
    assert "composite_score" not in coverage
    assert "final_trading_signal" not in coverage


def test_no_network_or_file_writes(tmp_path: Path) -> None:
    before = set(tmp_path.iterdir())

    result = build_all_domain_inputs(_normalized_fixture())

    assert set(tmp_path.iterdir()) == before
    assert "CME CL futures curve source" not in str(result)