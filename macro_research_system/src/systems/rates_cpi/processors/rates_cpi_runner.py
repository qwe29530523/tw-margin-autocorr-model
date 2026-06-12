from __future__ import annotations

from pathlib import Path

from src.common.dates import today_taipei
from src.common.io import ensure_dir, write_json
from src.common.settings import Settings, load_settings
from src.systems.rates_cpi.charts.rates_cpi_charts import (
    write_cpi_component_trend_chart,
    write_cpi_nowcast_chart,
    write_rates_cpi_dashboard_chart,
    write_rates_curve_chart,
)
from src.systems.rates_cpi.fetchers.bls_fetcher import fetch_bls_cpi_components
from src.systems.rates_cpi.fetchers.fred_fetcher import fetch_fred_rates_frame
from src.systems.rates_cpi.processors.cpi_nowcast_engine import build_cpi_nowcast
from src.systems.rates_cpi.processors.data_validation import validate_bls_components, validate_fred_rates_frame
from src.systems.rates_cpi.processors.rates_curve_engine import build_rates_metrics
from src.systems.rates_cpi.reports.rates_cpi_report import write_rates_cpi_report


SUMMARY_KEYS = [
    "system",
    "report_date",
    "data_source_mode",
    "fred_real_data",
    "bls_real_data",
    "mock_mode",
    "real_data_ready",
    "data_validation_passed",
    "rates_asof_date",
    "cpi_asof_month",
    "rates_regime",
    "funding_pressure_signal",
    "carry_signal",
    "curve_signal",
    "cpi_nowcast_signal",
    "fed_funds",
    "sofr",
    "rate_3m",
    "rate_1y",
    "rate_2y",
    "rate_5y",
    "rate_10y",
    "rate_30y",
    "spread_10y_3m",
    "spread_10y_2y",
    "spread_5y_2y",
    "spread_30y_10y",
    "sofr_fed_funds_spread",
    "three_month_fed_funds_spread",
    "headline_cpi_mom_nowcast",
    "headline_cpi_yoy_nowcast",
    "core_cpi_mom_nowcast",
    "core_cpi_yoy_nowcast",
    "data_completeness_score",
    "regime_confidence_score",
    "warnings",
]


def empty_rates_cpi_summary(report_date: str) -> dict:
    summary = {key: None for key in SUMMARY_KEYS}
    summary.update(
        {
            "system": "rates_cpi",
            "report_date": report_date,
            "data_source_mode": "Core FRED + BLS",
            "fred_real_data": False,
            "bls_real_data": False,
            "mock_mode": True,
            "real_data_ready": False,
            "data_validation_passed": False,
            "rates_regime": "unknown",
            "funding_pressure_signal": "unknown",
            "carry_signal": "unknown",
            "curve_signal": "unknown",
            "cpi_nowcast_signal": "unknown",
            "data_completeness_score": 0,
            "regime_confidence_score": 0,
            "warnings": [],
        }
    )
    return summary


def _settings_warnings(settings: Settings) -> list[str]:
    warnings = [
        f".env loaded: {str(settings.env_file_loaded).lower()}.",
        f"MOCK_MODE actual value: {str(settings.mock_mode).lower()}.",
        f"FRED_API_KEY present: {str(bool(settings.fred_api_key)).lower()}.",
        f"BLS_API_KEY present: {str(bool(settings.bls_api_key)).lower()}.",
    ]
    if settings.mock_mode:
        warnings.append("MOCK DATA ONLY: MOCK_MODE=true.")
    if not settings.fred_api_key:
        warnings.append("FRED_API_KEY missing; FRED rates data will use mock mode.")
    if not settings.bls_api_key:
        warnings.append("BLS_API_KEY missing; BLS CPI data will use mock mode.")
    return warnings


def _score_completeness(summary: dict) -> int:
    required = [
        "fed_funds",
        "sofr",
        "rate_3m",
        "rate_2y",
        "rate_10y",
        "spread_10y_3m",
        "headline_cpi_mom_nowcast",
        "core_cpi_mom_nowcast",
    ]
    available = sum(summary.get(key) is not None for key in required)
    return int(round(available / len(required) * 100))


def build_rates_cpi_summary(
    fred_frame,
    bls_components: dict,
    warnings: list[str],
    fred_source_mode: str,
    bls_source_mode: str,
) -> dict:
    summary = empty_rates_cpi_summary(today_taipei().isoformat())
    rates = build_rates_metrics(fred_frame)
    cpi = build_cpi_nowcast(bls_components)
    summary.update(rates)
    summary.update({key: value for key, value in cpi.items() if key != "warnings"})
    fred_validation = validate_fred_rates_frame(fred_frame, fred_source_mode)
    bls_validation = validate_bls_components(bls_components, bls_source_mode)
    validation_warnings = fred_validation["warnings"] + bls_validation["warnings"]
    summary["fred_real_data"] = bool(fred_validation["real_data"])
    summary["bls_real_data"] = bool(bls_validation["real_data"])
    summary["real_data_ready"] = bool(summary["fred_real_data"] and summary["bls_real_data"])
    summary["data_validation_passed"] = bool(summary["real_data_ready"] and not validation_warnings)
    summary["mock_mode"] = not summary["real_data_ready"] or fred_source_mode != "real" or bls_source_mode != "real"
    summary["warnings"] = list(dict.fromkeys(warnings + cpi.get("warnings", []) + validation_warnings))
    if summary["mock_mode"] and not any("MOCK DATA ONLY" in item for item in summary["warnings"]):
        summary["warnings"].insert(0, "MOCK DATA ONLY: rates_cpi is not ready for interpretation.")
    summary["data_completeness_score"] = _score_completeness(summary)
    summary["regime_confidence_score"] = 0 if not summary["real_data_ready"] else min(100, 45 + round(summary["data_completeness_score"] * 0.45))
    return {key: summary.get(key) for key in SUMMARY_KEYS}


def run_rates_cpi(data_root: Path) -> dict:
    settings = load_settings()
    warnings = _settings_warnings(settings)
    fred_frame, fred_warnings, fred_source_mode = fetch_fred_rates_frame(settings)
    bls_components, bls_warnings, bls_source_mode = fetch_bls_cpi_components(settings)
    warnings.extend(
        [
            f"FRED request success: {str(fred_source_mode == 'real').lower()}; source_mode={fred_source_mode}.",
            f"BLS request success: {str(bls_source_mode == 'real').lower()}; source_mode={bls_source_mode}.",
        ]
    )
    warnings.extend(fred_warnings + bls_warnings)
    summary = build_rates_cpi_summary(fred_frame, bls_components, warnings, fred_source_mode, bls_source_mode)
    base = ensure_dir(data_root / "rates_cpi")
    raw = ensure_dir(base / "raw")
    fred_frame.to_csv(raw / "fred_rates_frame.csv", index=False)
    write_json(raw / "bls_cpi_components.json", bls_components)
    write_json(base / "processed" / "rates_cpi_summary.json", summary)
    charts = ensure_dir(base / "charts")
    mock_label = not summary["real_data_ready"]
    write_rates_curve_chart(fred_frame, charts / "rates_curve.png", mock_data_only=mock_label)
    write_cpi_nowcast_chart(summary, charts / "cpi_nowcast.png", mock_data_only=mock_label)
    write_cpi_component_trend_chart(bls_components, charts / "cpi_component_trends.png", mock_data_only=mock_label)
    write_rates_cpi_dashboard_chart(fred_frame, summary, charts / "rates_cpi_dashboard.png", mock_data_only=mock_label)
    write_rates_cpi_report(summary, base / "reports")
    return summary
