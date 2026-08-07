from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.systems.oil_market.calculate_crack_spread_research import calculate_research_crack_spreads


FORBIDDEN_COLUMNS = {
    "production_score",
    "composite_score",
    "final_trading_signal",
    "trading_signal",
}


def _price_fixture() -> pd.DataFrame:
    rows = [
        ("2026-01-02", "CL=F", 75.0),
        ("2026-01-02", "RB=F", 2.25),
        ("2026-01-02", "HO=F", 2.40),
        ("2026-01-05", "CL=F", 76.0),
        ("2026-01-05", "RB=F", 2.30),
        ("2026-01-05", "HO=F", 2.45),
    ]
    return pd.DataFrame(rows, columns=["date", "symbol", "close"])


def test_calculate_research_crack_spreads_uses_gallon_to_barrel_conversion() -> None:
    result = calculate_research_crack_spreads(_price_fixture())
    latest = result.loc[result["date"].eq(pd.Timestamp("2026-01-05"))].iloc[0]

    assert latest["wti_front_month_proxy"] == 76.0
    assert latest["rbob_front_month_proxy"] == 2.30
    assert latest["heating_oil_front_month_proxy"] == 2.45
    assert latest["gasoline_crack_research_proxy"] == (2.30 * 42) - 76.0
    assert latest["distillate_crack_research_proxy"] == (2.45 * 42) - 76.0
    assert latest["crack_321_research_proxy"] == (((2 * 2.30 * 42) + (2.45 * 42) - (3 * 76.0)) / 3)
    assert set(result["source_name"]) == {"YAHOO_YFINANCE"}
    assert set(result["source_type"]) == {"research_only_public_proxy"}
    assert set(result["data_status"]) == {"RESEARCH_ONLY"}
    assert FORBIDDEN_COLUMNS.isdisjoint(result.columns)


def test_calculate_research_crack_spreads_leaves_missing_prices_as_nan() -> None:
    frame = _price_fixture()
    frame.loc[frame["symbol"].eq("RB=F"), "close"] = pd.NA

    result = calculate_research_crack_spreads(frame)

    assert result["gasoline_crack_research_proxy"].isna().all()
    assert result["crack_321_research_proxy"].isna().all()
    assert result["distillate_crack_research_proxy"].notna().all()


def test_calculator_does_not_write_files(tmp_path: Path) -> None:
    before = set(tmp_path.iterdir())

    result = calculate_research_crack_spreads(_price_fixture())

    assert not result.empty
    assert set(tmp_path.iterdir()) == before
