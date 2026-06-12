from __future__ import annotations

from pathlib import Path

from src.common.dates import today_taipei
from src.common.io import ensure_dir, write_json
from src.common.scoring import clamp_score
from src.common.settings import load_settings
from src.systems.oil_rates_cpi.fetchers.bls_fetcher import fetch_bls_cpi
from src.systems.oil_rates_cpi.fetchers.eia_fetcher import fetch_eia_series
from src.systems.oil_rates_cpi.fetchers.fred_fetcher import fetch_fred_series
from src.systems.oil_rates_cpi.processors.cpi_nowcast import build_cpi_nowcast
from src.systems.oil_rates_cpi.processors.oil_engine import build_oil_metrics
from src.systems.oil_rates_cpi.processors.rates_curve_engine import build_rates_curve_metrics
from src.systems.oil_rates_cpi.reports.oil_rates_cpi_report import write_oil_rates_cpi_report


def _macro_regime(oil: dict, rates: dict, cpi: dict) -> tuple[str, str]:
    if cpi["cpi_nowcast_signal"] == "inflationary" and rates["funding_pressure_signal"] in {
        "funding_pressure_elevated",
        "funding_pressure_stress",
    }:
        return "inflation_pressure", "none"
    if oil["product_demand_signal"].startswith("product_demand_softening") and rates["carry_signal"] == "carry_repair":
        return "neutral_mixed", "disinflation_with_bond_support"
    return "neutral_mixed", "none"


def build_oil_rates_cpi_summary(mock_mode: bool | None = None) -> dict:
    settings = load_settings()
    if mock_mode is not None:
        settings = type(settings)(
            fred_api_key=settings.fred_api_key,
            eia_api_key=settings.eia_api_key,
            bls_api_key=settings.bls_api_key,
            use_yahoo=settings.use_yahoo,
            mock_mode=mock_mode,
        )
    fred, fred_warnings = fetch_fred_series(settings)
    eia, eia_warnings = fetch_eia_series(settings)
    bls, bls_warnings = fetch_bls_cpi(settings)
    oil = build_oil_metrics(eia)
    rates = build_rates_curve_metrics(fred)
    cpi = build_cpi_nowcast(bls)
    macro_regime, secondary_regime = _macro_regime(oil, rates, cpi)
    warnings = settings.warnings + fred_warnings + eia_warnings + bls_warnings + cpi["warnings"]
    data_completeness = 100 if settings.mock_mode else 70
    regime_confidence = clamp_score(65 + cpi["confidence_score"] * 0.2 - len(warnings))
    summary = {
        "system": "oil_rates_cpi",
        "mock_mode": settings.mock_mode,
        "report_date": today_taipei().isoformat(),
        "data_source_mode": "Core FRED + EIA + BLS",
        "yahoo_overlay": settings.use_yahoo,
        "data_completeness_score": data_completeness,
        "regime_confidence_score": regime_confidence,
        "macro_regime": macro_regime,
        "secondary_regime": secondary_regime,
        "oil_regime": oil["oil_regime"],
        "inventory_signal": oil["inventory_signal"],
        "product_demand_signal": oil["product_demand_signal"],
        "supply_signal": oil["supply_signal"],
        "rates_regime": rates["rates_regime"],
        "funding_pressure_signal": rates["funding_pressure_signal"],
        "carry_signal": rates["carry_signal"],
        "cpi_nowcast_signal": cpi["cpi_nowcast_signal"],
        "headline_cpi_mom_nowcast": cpi["headline_cpi_mom_nowcast"],
        "headline_cpi_yoy_nowcast": cpi["headline_cpi_yoy_nowcast"],
        "core_cpi_mom_nowcast": cpi["core_cpi_mom_nowcast"],
        "core_cpi_yoy_nowcast": cpi["core_cpi_yoy_nowcast"],
        "warnings": warnings,
    }
    summary.update(oil)
    summary.update(rates)
    summary.update({key: value for key, value in cpi.items() if key not in {"used_fields", "warnings"}})
    return summary


def run_oil_rates_cpi(data_root: Path) -> dict:
    summary = build_oil_rates_cpi_summary()
    base = ensure_dir(data_root / "oil_rates_cpi")
    write_json(base / "processed" / "oil_rates_cpi_summary.json", summary)
    write_oil_rates_cpi_report(summary, base / "reports")
    return summary
