from src.reports.markdown_report import render_markdown_report


def test_report_includes_asof_dates_and_human_readable_inventory_units():
    summary = {
        "regime": "neutral_mixed",
        "data_completeness_score": 72,
        "regime_confidence_score": 42,
        "reasons": ["測試理由"],
        "warnings": ["Rates data incomplete; using latest valid observation or lowering confidence."],
    }
    metrics = {
        "oil_price_asof_date": "2026-06-07",
        "fred_rates_asof_date": "2026-06-05",
        "rates_curve_asof_date": "2026-06-04",
        "eia_inventory_asof_date": "2026-05-29",
        "crack_spread_asof_date": "2026-06-07",
        "ten_year": None,
        "two_year": None,
        "crude_inventory_4w_change": -23470,
        "crude_exports": 5123,
        "crude_production": 13400,
    }

    report = render_markdown_report(summary, metrics, "2026-06-08")

    assert "Oil price as-of date: 2026-06-07" in report
    assert "FRED rates as-of date: 2026-06-05" in report
    assert "Rates curve as-of date: 2026-06-04" in report
    assert "EIA inventory as-of date: 2026-05-29" in report
    assert "Crack spread as-of date: 2026-06-07" in report
    assert "10Y: missing" in report
    assert "Crude inventory 4W change: -23.47 million barrels" in report
    assert "Crude exports: 5.12 million barrels/day" in report
    assert "Crude production: 13.40 million barrels/day" in report


def test_report_interpretation_mentions_mixed_supply_demand_signal():
    summary = {
        "regime": "neutral_mixed",
        "data_completeness_score": 90,
        "regime_confidence_score": 57,
        "reasons": [],
        "warnings": [],
    }
    metrics = {
        "inventory_signal": "inventory_tightening",
        "crack_signal": "demand_weakening",
    }

    report = render_markdown_report(summary, metrics, "2026-06-08")

    assert "庫存偏緊，但產品端需求動能轉弱，屬於供需混合訊號。" in report


def test_report_shows_secondary_regime_and_crack_momentum_fields():
    summary = {
        "regime": "neutral_mixed",
        "secondary_regime": "tight_inventory_weak_products",
        "data_completeness_score": 90,
        "regime_confidence_score": 57,
        "reasons": [],
        "warnings": [],
    }
    metrics = {
        "gasoline_crack_20d_change": -2.25,
        "diesel_crack_20d_change": -3.50,
        "gasoline_crack_20d_ma": 22.10,
        "diesel_crack_20d_ma": 35.25,
        "diesel_crack": 34.0,
        "crack_signal": "demand_weakening",
        "inventory_signal": "inventory_tightening",
    }

    report = render_markdown_report(summary, metrics, "2026-06-08")

    assert "Secondary Regime: tight_inventory_weak_products" in report
    assert "Gasoline crack 20D change: -2.25" in report
    assert "Diesel crack 20D change: -3.50" in report
    assert "Gasoline crack 20D MA: 22.10" in report
    assert "Diesel crack 20D MA: 35.25" in report
    assert "裂解價差絕對水位仍高，但近期動能轉弱，因此模型判定為 demand_weakening。" in report


def test_report_hides_crude_exports_when_units_are_not_thousand_barrels_per_day():
    summary = {
        "regime": "neutral_mixed",
        "data_completeness_score": 70,
        "regime_confidence_score": 42,
        "reasons": [],
        "warnings": [],
    }
    metrics = {
        "crude_exports": 13295,
        "crude_exports_units": "MBBL",
    }

    report = render_markdown_report(summary, metrics, "2026-06-08")

    assert "Crude exports: missing" in report


def test_report_uses_core_fred_eia_framework_format():
    summary = {
        "macro_regime": "neutral_mixed",
        "secondary_regime": "tight_inventory_weak_products",
        "data_completeness_score": 86,
        "regime_confidence_score": 57,
        "reasons": ["測試核心判斷"],
        "warnings": ["Yahoo overlay OFF"],
        "metrics": {
            "oil_price_asof_date": "2026-06-05",
            "fred_rates_asof_date": "10Y 2026-06-04",
            "rates_curve_asof_date": "2026-06-04",
            "eia_inventory_asof_date": "2026-05-29",
            "wti": 90.0,
            "brent": 94.0,
            "brent_wti_spread": 4.0,
            "curve_state": "unknown",
            "gasoline_product_supplied_4w_change": -100,
            "distillate_product_supplied_4w_change": -50,
            "jet_fuel_product_supplied_4w_change": 10,
            "product_demand_signal": "demand_weakening",
            "fedfunds": 4.25,
            "sofr": 4.35,
            "ten_year": 4.5,
            "two_year": 4.1,
            "ten_year_sofr_carry_proxy": 0.15,
        },
    }

    report = render_markdown_report(summary, summary["metrics"], "2026-06-08")

    assert "Data source mode: Core FRED + EIA" in report
    assert "Yahoo overlay: OFF" in report
    assert "Macro Regime: neutral_mixed" in report
    assert "Secondary Regime: tight_inventory_weak_products" in report
    assert "Data completeness score: 86" in report
    assert "Regime confidence score: 57" in report
    assert "## 4. 成品需求" in report
    assert "## 5. 利率曲線與資金成本" in report


def test_report_shows_curve_spread_asof_and_belly_dynamic_fields():
    summary = {
        "macro_regime": "neutral_mixed",
        "data_completeness_score": 88,
        "regime_confidence_score": 52,
        "reasons": [],
        "warnings": [],
    }
    metrics = {
        "rates_curve_asof_date": "2026-06-04",
        "ten_year_three_month_spread": 0.75,
        "ten_year_two_year_spread": 0.38,
        "five_year_two_year_spread": 0.13,
        "ten_year_five_year_spread": 0.25,
        "thirty_year_ten_year_spread": 0.50,
        "two_year_change_20d": -0.05,
        "five_year_change_20d": 0.30,
        "ten_year_change_20d": 0.03,
        "thirty_year_change_20d": 0.02,
        "belly_relative_move": 0.26,
    }

    report = render_markdown_report(summary, metrics, "2026-06-08")

    assert "10Y-3M: 0.75 (as-of 2026-06-04)" in report
    assert "10Y-2Y: 0.38 (as-of 2026-06-04)" in report
    assert "2Y 20D change: -0.05" in report
    assert "5Y 20D change: 0.30" in report
    assert "10Y 20D change: 0.03" in report
    assert "30Y 20D change: 0.02" in report
    assert "belly_relative_move: 0.26" in report


def test_report_shows_official_fred_spread_reference_asof_dates_when_available():
    summary = {
        "macro_regime": "neutral_mixed",
        "data_completeness_score": 88,
        "regime_confidence_score": 52,
        "reasons": [],
        "warnings": [],
    }
    metrics = {
        "ten_year_two_year_spread_fred": 0.40,
        "ten_year_two_year_spread_fred_asof_date": "2026-06-05",
        "ten_year_three_month_spread_fred": 0.72,
        "ten_year_three_month_spread_fred_asof_date": "2026-06-04",
    }

    report = render_markdown_report(summary, metrics, "2026-06-08")

    assert "Official FRED spread reference" in report
    assert "T10Y2Y: 0.40 (as-of 2026-06-05)" in report
    assert "T10Y3M: 0.72 (as-of 2026-06-04)" in report
