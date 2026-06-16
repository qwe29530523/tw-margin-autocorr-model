from __future__ import annotations

import os
import urllib.error

import pytest

from src.systems.oil_market.fetchers import metalprice_energy_benchmark_fetcher as fetcher


FORBIDDEN_OUTPUT_COLUMNS = {
    "cl_m1_settle",
    "cl_m2_settle",
    "cl_m3_settle",
    "curve_state",
    "production_score",
    "composite_score",
    "inflation_pressure_score",
    "oil_curve_score",
}


def _latest_payload() -> dict:
    return {
        "success": True,
        "base": "USD",
        "timestamp": 1_782_000_000,
        "rates": {
            "WTI": 76.25,
            "BRENT": 81.40,
            "NATURALGAS": 3.12,
            "GASOLINE": 2.48,
        },
    }


def test_missing_metalprice_api_key_raises_clear_error_without_key(monkeypatch) -> None:
    monkeypatch.delenv("METALPRICE_API_KEY", raising=False)

    with pytest.raises(fetcher.MetalPriceAPIError) as error:
        fetcher.fetch_latest_energy_benchmarks()

    assert "METALPRICE_API_KEY is required" in str(error.value)
    assert "secret-key" not in str(error.value)


def test_latest_response_normalizes_wti_and_brent_rows(monkeypatch) -> None:
    calls: list[dict] = []

    def fake_request(url: str, api_key: str, timeout: int) -> dict:
        calls.append({"url": url, "api_key": api_key, "timeout": timeout})
        return _latest_payload()

    monkeypatch.setenv("METALPRICE_API_KEY", "secret-key")
    monkeypatch.setattr(fetcher, "_request_json", fake_request)

    frame = fetcher.fetch_latest_energy_benchmarks(symbols=["WTI", "BRENT"], base="USD")

    assert set(frame["symbol"]) == {"WTI", "BRENT"}
    assert set(frame["source"]) == {"MetalPriceAPI"}
    assert set(frame["source_type"]) == {"research_only_benchmark"}
    assert set(frame["base"]) == {"USD"}
    assert {"date", "symbol", "price", "base", "source", "source_type", "fetched_at", "raw_timestamp"}.issubset(
        frame.columns
    )
    assert FORBIDDEN_OUTPUT_COLUMNS.isdisjoint(frame.columns)
    assert calls
    assert calls[0]["api_key"] == "secret-key"
    assert "secret-key" not in calls[0]["url"]


def test_historical_response_normalizes_requested_date(monkeypatch) -> None:
    def fake_request(url: str, api_key: str, timeout: int) -> dict:
        assert "2026-06-12" in url
        return {
            "success": True,
            "base": "USD",
            "date": "2026-06-12",
            "rates": {"WTI": 74.5},
        }

    monkeypatch.setenv("METALPRICE_API_KEY", "secret-key")
    monkeypatch.setattr(fetcher, "_request_json", fake_request)

    frame = fetcher.fetch_historical_energy_benchmarks("2026-06-12", symbols=["WTI"])

    assert len(frame) == 1
    assert frame.iloc[0]["date"].strftime("%Y-%m-%d") == "2026-06-12"
    assert frame.iloc[0]["symbol"] == "WTI"
    assert frame.iloc[0]["price"] == 74.5
    assert frame.iloc[0]["source_type"] == "research_only_benchmark"


def test_api_error_response_is_handled_without_leaking_key(monkeypatch) -> None:
    def fake_request(url: str, api_key: str, timeout: int) -> dict:
        raise fetcher.MetalPriceAPIError("MetalPriceAPI auth error: HTTP 401")

    monkeypatch.setenv("METALPRICE_API_KEY", "secret-key")
    monkeypatch.setattr(fetcher, "_request_json", fake_request)

    with pytest.raises(fetcher.MetalPriceAPIError) as error:
        fetcher.fetch_latest_energy_benchmarks()

    assert "HTTP 401" in str(error.value)
    assert "secret-key" not in str(error.value)


def test_malformed_or_empty_response_is_controlled(monkeypatch) -> None:
    def fake_request(url: str, api_key: str, timeout: int) -> dict:
        return {"success": True, "base": "USD", "rates": {}}

    monkeypatch.setenv("METALPRICE_API_KEY", "secret-key")
    monkeypatch.setattr(fetcher, "_request_json", fake_request)

    with pytest.raises(fetcher.MetalPriceAPIError) as error:
        fetcher.fetch_latest_energy_benchmarks(symbols=["WTI"])

    assert "no data" in str(error.value).lower()
    assert "secret-key" not in str(error.value)


def test_unsupported_symbol_is_rejected_before_request(monkeypatch) -> None:
    monkeypatch.setenv("METALPRICE_API_KEY", "secret-key")

    with pytest.raises(fetcher.MetalPriceAPIError) as error:
        fetcher.fetch_latest_energy_benchmarks(symbols=["CL_M1"])

    assert "unsupported symbol" in str(error.value).lower()
    assert "CL_M1" in str(error.value)


def test_request_uses_header_not_query_string_and_masks_quota_error(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return b'{"success": true, "base": "USD", "rates": {"WTI": 70.0}}'

    def fake_urlopen(request, timeout: int):
        captured["url"] = request.full_url
        captured["headers"] = {key.lower(): value for key, value in request.header_items()}
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(fetcher.urllib.request, "urlopen", fake_urlopen)

    payload = fetcher._request_json("https://example.test/latest?base=USD", "secret-key", timeout=7)

    assert payload["rates"]["WTI"] == 70.0
    assert captured["headers"]["x-api-key"] == "secret-key"
    assert "secret-key" not in captured["url"]
    assert captured["timeout"] == 7

    def fake_quota_error(request, timeout: int):
        raise urllib.error.HTTPError(
            url=request.full_url,
            code=429,
            msg="quota exceeded",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(fetcher.urllib.request, "urlopen", fake_quota_error)

    with pytest.raises(fetcher.MetalPriceAPIError) as error:
        fetcher._request_json("https://example.test/latest?base=USD", "secret-key", timeout=7)

    assert "quota exceeded" in str(error.value)
    assert "secret-key" not in str(error.value)


def test_tests_do_not_require_real_network_or_real_key(monkeypatch) -> None:
    def fail_if_called(url: str, api_key: str, timeout: int) -> dict:
        raise AssertionError("real HTTP call should not be used in tests")

    monkeypatch.setenv("METALPRICE_API_KEY", "test-key")
    monkeypatch.setattr(fetcher, "_request_json", fail_if_called)

    with pytest.raises(AssertionError, match="real HTTP call should not be used"):
        fetcher.fetch_latest_energy_benchmarks()

    assert os.getenv("METALPRICE_API_KEY") == "test-key"
