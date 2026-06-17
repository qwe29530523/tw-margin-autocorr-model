from __future__ import annotations

import urllib.request
from pathlib import Path

from src.systems.common.api_key_preflight import run_api_key_preflight


ENV_KEYS = {
    "FRED_API_KEY": "fred-dummy-value",
    "BLS_API_KEY": "bls-dummy-value",
    "EIA_API_KEY": "eia-dummy-value",
    "METALPRICE_API_KEY": "metalprice-dummy-value",
    "CENSUS_API_KEY": "census-dummy-value",
}

FORBIDDEN_SCORE_NAMES = {
    "production_score",
    "composite_score",
    "inflation_pressure_score",
}


def _write_registry(path: Path) -> Path:
    path.write_text(
        """
FRED:
  source_name: FRED
  source_type: official_public_macro
  api_key_env: FRED_API_KEY
  usable_for:
    - rates
BLS:
  source_name: BLS
  source_type: official_public_labor_inflation
  api_key_env: BLS_API_KEY
  usable_for:
    - CPI components
EIA:
  source_name: EIA
  source_type: official_public_energy
  api_key_env: EIA_API_KEY
  usable_for:
    - crude oil inventory
MetalPriceAPI:
  source_name: MetalPriceAPI
  source_type: research_only_benchmark
  api_key_env: METALPRICE_API_KEY
  usable_for:
    - WTI benchmark
  not_usable_for:
    - WTI M1/M2/M3 futures curve
Census:
  source_name: Census
  source_type: official_public_real_economy
  api_key_env: CENSUS_API_KEY
  usable_for:
    - housing starts
CME DataMine:
  source_name: CME DataMine
  source_type: official_datamine
  api_key_env: null
  status: pending_vendor_or_licensed_delivery
  usable_for:
    - CL individual contract-month settlement
  blocker_status: open
""".strip(),
        encoding="utf-8",
    )
    return path


def _as_by_name(results: list[dict]) -> dict[str, dict]:
    return {item["source_name"]: item for item in results}


def test_env_keys_are_reported_as_configured_without_values(tmp_path: Path, monkeypatch) -> None:
    registry_path = _write_registry(tmp_path / "api_source_registry.yaml")
    for key, value in ENV_KEYS.items():
        monkeypatch.setenv(key, value)

    results = run_api_key_preflight(repo_root=tmp_path, registry_path=registry_path)
    by_name = _as_by_name(results)

    assert by_name["FRED"]["is_configured"] is True
    assert by_name["BLS"]["is_configured"] is True
    assert by_name["EIA"]["is_configured"] is True
    assert by_name["MetalPriceAPI"]["is_configured"] is True
    assert by_name["Census"]["is_configured"] is True
    assert by_name["FRED"]["configured_by"] == "FRED_API_KEY"
    assert all(value not in str(results) for value in ENV_KEYS.values())


def test_missing_env_returns_false_safely(tmp_path: Path, monkeypatch) -> None:
    registry_path = _write_registry(tmp_path / "api_source_registry.yaml")
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    results = run_api_key_preflight(repo_root=tmp_path, registry_path=registry_path)
    by_name = _as_by_name(results)

    assert by_name["FRED"]["is_configured"] is False
    assert by_name["FRED"]["configured_by"] is None
    assert by_name["FRED"]["missing_reason"] == "MISSING_ENV"


def test_root_dotenv_can_configure_key_without_returning_value(tmp_path: Path, monkeypatch) -> None:
    registry_path = _write_registry(tmp_path / "api_source_registry.yaml")
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    env_name = "FRED_API_KEY"
    dotenv_value = "fred-dotenv-dummy-value"
    (tmp_path / ".env").write_text(f"{env_name}={dotenv_value}\n", encoding="utf-8")

    results = run_api_key_preflight(repo_root=tmp_path, registry_path=registry_path)
    fred = _as_by_name(results)["FRED"]

    assert fred["is_configured"] is True
    assert fred["configured_by"] == "FRED_API_KEY"
    assert dotenv_value not in str(results)


def test_cme_datamine_remains_open_blocker_without_api_key(tmp_path: Path, monkeypatch) -> None:
    registry_path = _write_registry(tmp_path / "api_source_registry.yaml")
    monkeypatch.delenv("CME_DATAMINE_API_KEY", raising=False)

    results = run_api_key_preflight(repo_root=tmp_path, registry_path=registry_path)
    cme = _as_by_name(results)["CME DataMine"]

    assert cme["primary_env"] is None
    assert cme["is_configured"] is False
    assert cme["missing_reason"] == "PENDING_VENDOR_OR_LICENSED_DELIVERY"
    assert cme["blocker_status"] == "open"


def test_metalpriceapi_remains_research_only(tmp_path: Path, monkeypatch) -> None:
    registry_path = _write_registry(tmp_path / "api_source_registry.yaml")
    metalprice_value = "metalprice-dummy-value"
    monkeypatch.setenv("METALPRICE_API_KEY", metalprice_value)

    results = run_api_key_preflight(repo_root=tmp_path, registry_path=registry_path)
    metalprice = _as_by_name(results)["MetalPriceAPI"]

    assert metalprice["source_type"] == "research_only_benchmark"
    assert metalprice["is_configured"] is True
    assert metalprice_value not in str(metalprice)


def test_preflight_has_safe_schema_no_scores_and_no_network(tmp_path: Path, monkeypatch) -> None:
    registry_path = _write_registry(tmp_path / "api_source_registry.yaml")

    def fail_network(*args, **kwargs):
        raise AssertionError("preflight must not call network")

    monkeypatch.setattr(urllib.request, "urlopen", fail_network)
    fred_value = "fred-dummy-value"
    monkeypatch.setenv("FRED_API_KEY", fred_value)

    results = run_api_key_preflight(repo_root=tmp_path, registry_path=registry_path)

    assert results
    assert set(results[0]) == {
        "source_name",
        "source_type",
        "primary_env",
        "is_configured",
        "configured_by",
        "missing_reason",
        "blocker_status",
    }
    assert all(name not in str(results) for name in FORBIDDEN_SCORE_NAMES)
    assert fred_value not in str(results)
