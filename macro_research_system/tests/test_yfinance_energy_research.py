from __future__ import annotations

import builtins
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from src.systems.oil_market import fetch_yfinance_energy_research as fetcher


FORBIDDEN_COLUMNS = {
    "production_score",
    "composite_score",
    "final_trading_signal",
    "trading_signal",
    "cl_m1_settle",
    "cl_m2_settle",
    "cl_m3_settle",
    "curve_state",
}


def _mock_download(symbols, start=None, end=None, progress=False, auto_adjust=False):
    assert symbols == ["CL=F", "RB=F", "HO=F"]
    assert start == "2026-01-01"
    assert end == "2026-01-05"
    assert progress is False
    assert auto_adjust is False
    columns = pd.MultiIndex.from_product([["Close"], symbols])
    return pd.DataFrame(
        [
            [75.0, 2.25, 2.40],
            [76.0, 2.30, 2.45],
        ],
        index=pd.to_datetime(["2026-01-02", "2026-01-05"]),
        columns=columns,
    )


def test_fetch_yfinance_energy_research_prices_uses_mocked_yfinance(monkeypatch) -> None:
    monkeypatch.setitem(__import__("sys").modules, "yfinance", SimpleNamespace(download=_mock_download))

    frame = fetcher.fetch_yfinance_energy_research_prices(start="2026-01-01", end="2026-01-05")

    assert set(frame["symbol"]) == {"CL=F", "RB=F", "HO=F"}
    assert set(frame["source_name"]) == {"YAHOO_YFINANCE"}
    assert set(frame["source_type"]) == {"research_only_public_proxy"}
    assert set(frame["data_status"]) == {"RESEARCH_ONLY"}
    assert {"date", "symbol", "close", "source_name", "source_type", "data_status", "caveat"} <= set(frame.columns)
    assert FORBIDDEN_COLUMNS.isdisjoint(frame.columns)
    assert "api-key-dummy-value" not in frame.to_string()


def test_fetcher_does_not_read_env_or_write_files(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setitem(__import__("sys").modules, "yfinance", SimpleNamespace(download=_mock_download))

    def fail_getenv(*args, **kwargs):  # pragma: no cover - called only on failure
        raise AssertionError("fetcher must not read .env or environment variables")

    monkeypatch.setattr(fetcher.os, "getenv", fail_getenv)
    before = set(tmp_path.iterdir())

    frame = fetcher.fetch_yfinance_energy_research_prices(start="2026-01-01", end="2026-01-05")

    assert not frame.empty
    assert set(tmp_path.iterdir()) == before


def test_missing_yfinance_raises_safe_runtime_error(monkeypatch) -> None:
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "yfinance":
            raise ImportError("module missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(RuntimeError) as error:
        fetcher.fetch_yfinance_energy_research_prices()

    message = str(error.value)
    assert "yfinance" in message
    assert "api-key-dummy-value" not in message
    assert "SECRET" not in message
