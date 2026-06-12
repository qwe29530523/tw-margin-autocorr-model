from __future__ import annotations

from pathlib import Path
import math

from src.common.dates import today_taipei
from src.common.io import ensure_dir, write_json
from src.common.settings import Settings, load_settings
from src.systems.oil_market.charts.oil_crack_spread_chart import write_oil_crack_spread_chart
from src.systems.oil_market.charts.oil_dashboard_chart import write_oil_dashboard_chart
from src.systems.oil_market.charts.oil_inventory_chart import write_oil_inventory_chart
from src.systems.oil_market.charts.oil_price_chart import write_oil_price_chart
from src.systems.oil_market.charts.oil_product_demand_chart import write_oil_product_demand_chart
from src.systems.oil_market.fetchers.eia_fetcher import fetch_eia_oil_frame
from src.systems.oil_market.fetchers.fred_fetcher import fetch_oil_price_frame
from src.systems.oil_market.processors.crack_spread_engine import build_crack_spread_metrics
from src.systems.oil_market.processors.data_validation import (
    MOCK_BANNER,
    validate_eia_frame,
    validate_fred_frame,
    write_data_validation_log,
)
from src.systems.oil_market.processors.inventory_engine import build_inventory_metrics
from src.systems.oil_market.processors.oil_price_engine import build_oil_price_metrics
from src.systems.oil_market.processors.oil_regime_engine import (
    SUMMARY_KEYS,
    classify_oil_regime,
    empty_oil_summary,
    score_data_completeness,
    score_regime_confidence,
)
from src.systems.oil_market.processors.product_demand_engine import build_product_demand_metrics
from src.systems.oil_market.processors.refinery_engine import build_refinery_metrics
from src.systems.oil_market.processors.supply_engine import build_supply_metrics
from src.systems.oil_market.reports.oil_market_report import write_oil_market_report


def _oil_market_settings_warnings(settings: Settings) -> list[str]:
    warnings: list[str] = []
    env_status = "true" if settings.env_file_loaded else "false"
    env_path = f" ({settings.env_file_path})" if settings.env_file_path else ""
    warnings.append(f".env loaded: {env_status}{env_path}.")
    warnings.append(f"MOCK_MODE actual value: {str(settings.mock_mode).lower()}.")
    warnings.append(f"FRED_API_KEY present: {str(bool(settings.fred_api_key)).lower()}.")
    warnings.append(f"EIA_API_KEY present: {str(bool(settings.eia_api_key)).lower()}.")
    if settings.mock_mode:
        warnings.append("MOCK_MODE=true; using oil market fixture data.")
    if not settings.fred_api_key:
        warnings.append("FRED_API_KEY missing; oil price data will use mock mode or missing warning.")
    if not settings.eia_api_key:
        warnings.append("EIA_API_KEY missing; petroleum data will use mock mode or missing warning.")
    return warnings


def _request_status_warning(label: str, source_mode: str) -> str:
    success = source_mode == "real"
    return f"{label} request success: {str(success).lower()}; source_mode={source_mode}."


def _summary_json_value(value):
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 6)
    return value


def build_oil_market_summary(
    price_frame,
    eia_frame,
    warnings: list[str],
    fred_source_mode: str = "mock",
    eia_source_mode: str = "mock",
) -> dict:
    report_date = today_taipei().isoformat()
    summary = empty_oil_summary(report_date)
    price_metrics = build_oil_price_metrics(price_frame)
    inventory_metrics = build_inventory_metrics(eia_frame)
    demand_metrics = build_product_demand_metrics(eia_frame)
    crack_metrics = build_crack_spread_metrics(eia_frame, demand_metrics["product_demand_signal"])
    refinery_metrics = build_refinery_metrics(eia_frame)
    supply_metrics = build_supply_metrics(eia_frame, inventory_metrics["inventory_signal"])
    summary.update(price_metrics)
    summary.update(inventory_metrics)
    summary.update(demand_metrics)
    summary.update(crack_metrics)
    summary.update(refinery_metrics)
    summary.update(supply_metrics)
    fred_validation = validate_fred_frame(price_frame, fred_source_mode)
    eia_validation = validate_eia_frame(eia_frame, eia_source_mode)
    validation_warnings = fred_validation["warnings"] + eia_validation["warnings"]
    summary["fred_real_data"] = bool(fred_validation["real_data"])
    summary["eia_real_data"] = bool(eia_validation["real_data"])
    summary["real_data_ready"] = bool(summary["fred_real_data"] and summary["eia_real_data"])
    summary["data_validation_passed"] = bool(summary["real_data_ready"] and not validation_warnings)
    summary["data_validation_warnings"] = validation_warnings
    summary["data_source_mode"] = "Core FRED + EIA"
    if summary["real_data_ready"]:
        summary.update(classify_oil_regime(summary))
    else:
        summary["oil_regime"] = "mock_data_only"
        summary["price_war_risk"] = "low"
        summary["supply_shock_risk"] = "low"
        summary["demand_destruction_risk"] = "low"
    summary["warnings"] = list(dict.fromkeys(warnings))
    if not summary["real_data_ready"] and MOCK_BANNER not in summary["warnings"]:
        summary["warnings"].insert(0, MOCK_BANNER)
    summary["warnings"].extend(validation_warnings)
    summary["warnings"] = list(dict.fromkeys(summary["warnings"]))
    summary["mock_mode"] = not summary["real_data_ready"] or fred_source_mode != "real" or eia_source_mode != "real"
    summary["data_completeness_score"] = score_data_completeness(summary)
    summary["regime_confidence_score"] = min(score_regime_confidence(summary), 10) if not summary["real_data_ready"] else score_regime_confidence(summary)
    return {key: _summary_json_value(summary.get(key)) for key in SUMMARY_KEYS}


def run_oil_market(data_root: Path) -> dict:
    settings = load_settings()
    warnings = _oil_market_settings_warnings(settings)
    price_frame, fred_warnings, fred_source_mode = fetch_oil_price_frame(settings)
    eia_frame, eia_warnings, eia_source_mode = fetch_eia_oil_frame(settings)
    warnings.extend([_request_status_warning("FRED", fred_source_mode), _request_status_warning("EIA", eia_source_mode)])
    warnings.extend(fred_warnings + eia_warnings)
    base = ensure_dir(data_root / "oil_market")
    raw = ensure_dir(base / "raw")
    price_frame.to_csv(raw / "oil_price_frame.csv", index=False)
    eia_frame.to_csv(raw / "eia_oil_frame.csv", index=False)
    summary = build_oil_market_summary(price_frame, eia_frame, warnings, fred_source_mode, eia_source_mode)
    write_data_validation_log(base / "processed", validate_fred_frame(price_frame, fred_source_mode), validate_eia_frame(eia_frame, eia_source_mode))
    write_json(base / "processed" / "oil_market_summary.json", summary)
    charts = ensure_dir(base / "charts")
    mock_label = not summary["real_data_ready"]
    write_oil_price_chart(price_frame, charts / "oil_price_momentum.png", mock_data_only=mock_label)
    write_oil_inventory_chart(eia_frame, charts / "oil_inventory_proxy.png", mock_data_only=mock_label)
    write_oil_product_demand_chart(eia_frame, charts / "oil_product_demand.png", mock_data_only=mock_label)
    write_oil_crack_spread_chart(eia_frame, charts / "oil_crack_spread.png", mock_data_only=mock_label)
    write_oil_dashboard_chart(price_frame, eia_frame, charts / "oil_market_dashboard.png", mock_data_only=mock_label)
    write_oil_market_report(summary, base / "reports")
    return summary
