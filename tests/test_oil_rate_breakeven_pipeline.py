from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd

from oil_rate_macro_monitor.src.processors.rates_curve_engine import build_rates_curve_frame


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_fred_default_series_include_breakeven_inflation_inputs() -> None:
    fetcher_path = ROOT_DIR / "oil_rate_macro_monitor" / "src" / "fetchers" / "fred_fetcher.py"
    module = ast.parse(fetcher_path.read_text(encoding="utf-8"))
    default_series = next(
        node.value
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "DEFAULT_FRED_SERIES" for target in node.targets)
    )
    series_ids = [item.value for item in default_series.elts]

    assert "T5YIE" in series_ids
    assert "T10YIE" in series_ids


def test_rates_curve_engine_outputs_breakeven_columns_without_overwriting_yields() -> None:
    rows = []
    for idx, date in enumerate(pd.date_range("2026-01-01", periods=3)):
        rows.extend(
            [
                {"date": date, "series_id": "FEDFUNDS", "value": 3.5},
                {"date": date, "series_id": "SOFR", "value": 3.55},
                {"date": date, "series_id": "DGS3MO", "value": 3.7},
                {"date": date, "series_id": "DGS1", "value": 3.8},
                {"date": date, "series_id": "DGS2", "value": 4.0},
                {"date": date, "series_id": "DGS5", "value": 4.2},
                {"date": date, "series_id": "DGS10", "value": 4.5},
                {"date": date, "series_id": "DGS30", "value": 4.9},
                {"date": date, "series_id": "T5YIE", "value": 2.1 + idx * 0.01},
                {"date": date, "series_id": "T10YIE", "value": 2.3 + idx * 0.01},
            ]
        )

    result = build_rates_curve_frame(pd.DataFrame(rows))
    latest = result.iloc[-1]

    assert "breakeven_5y" in result.columns
    assert "breakeven_10y" in result.columns
    assert latest["five_year"] == 4.2
    assert latest["ten_year"] == 4.5
    assert latest["breakeven_5y"] == 2.12
    assert latest["breakeven_10y"] == 2.32
    assert str(pd.to_datetime(latest["breakeven_5y_asof_date"]).date()) == "2026-01-03"
    assert str(pd.to_datetime(latest["breakeven_10y_asof_date"]).date()) == "2026-01-03"
