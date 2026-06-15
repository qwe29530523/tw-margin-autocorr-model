from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from src.utils.dates import today_taipei
from src.utils.io import ensure_dirs


def write_markdown_report(summary: dict[str, Any], output_dir: Path) -> Path:
    ensure_dirs(output_dir)
    report_date = today_taipei()
    path = output_dir / f"oil_rate_macro_report_{report_date:%Y%m%d}.md"
    metrics = summary.get("metrics", {})
    content = render_markdown_report(summary, metrics, report_date.isoformat())
    path.write_text(content, encoding="utf-8")
    return path


def render_markdown_report(summary: dict[str, Any], metrics: dict[str, Any], report_date: str) -> str:
    macro_regime = summary.get("macro_regime", summary.get("regime", "neutral_mixed"))
    secondary_regime = summary.get("secondary_regime", "none")
    reasons = "\n".join(f"* {reason}" for reason in summary.get("reasons", [])) or "* 暫無明確核心判斷"
    warnings = "\n".join(f"* {warning}" for warning in report_warnings(summary, metrics)) or "* 無"
    return f"""# Oil + Rates Macro Monitor

日期：{report_date}
Data source mode: {metrics.get("data_source_mode", "Core FRED + EIA")}
Yahoo overlay: {metrics.get("yahoo_overlay", "OFF")}

## 1. 今日總結

* Macro Regime: {macro_regime}
* Secondary Regime: {secondary_regime}
* Data completeness score: {summary.get("data_completeness_score", summary.get("confidence_score", 0))}
* Regime confidence score: {summary.get("regime_confidence_score", summary.get("confidence_score", 0))}
* 核心判斷：
{reasons}

## 2. 油價

* Oil price as-of date: {_date_fmt(metrics.get("oil_price_asof_date"))}
* WTI: {_fmt(metrics.get("wti"))}
* Brent: {_fmt(metrics.get("brent"))}
* Brent-WTI spread: {_fmt(metrics.get("brent_wti_spread"))}
* WTI 5D / 20D / 60D: {_pct(metrics.get("wti_return_5d"))} / {_pct(metrics.get("wti_return_20d"))} / {_pct(metrics.get("wti_return_60d"))}
* Brent 5D / 20D / 60D: {_pct(metrics.get("brent_return_5d"))} / {_pct(metrics.get("brent_return_20d"))} / {_pct(metrics.get("brent_return_60d"))}
* Curve state: {metrics.get("curve_state", "unknown")}

## 3. 庫存與供給

* EIA inventory as-of date: {_date_fmt(metrics.get("eia_inventory_asof_date"))}
* Crude inventory 4W change: {_million_barrels(metrics.get("crude_inventory_4w_change"), metrics.get("crude_inventory_units"))}
* Gasoline inventory 4W change: {_million_barrels(metrics.get("gasoline_inventory_4w_change"), metrics.get("gasoline_inventory_units"))}
* Distillate inventory 4W change: {_million_barrels(metrics.get("distillate_inventory_4w_change"), metrics.get("distillate_inventory_units"))}
* Total inventory proxy 4W change: {_million_barrels(metrics.get("total_inventory_proxy_4w_change"), metrics.get("crude_inventory_units"))}
* Refinery utilization: {_percent_level(metrics.get("refinery_utilization"))}
* Refinery crude inputs: {_million_barrels_per_day(metrics.get("refinery_crude_inputs"), metrics.get("refinery_crude_inputs_units"))}
* Crude production: {_million_barrels_per_day(metrics.get("crude_production"), metrics.get("crude_production_units"))}
* Crude exports: {_million_barrels_per_day(metrics.get("crude_exports"), metrics.get("crude_exports_units"))}
* Inventory signal: {metrics.get("inventory_signal", "mixed")}
* Supply signal: {metrics.get("supply_signal", "mixed")}

## 4. 成品需求

* Crack spread as-of date: {_date_fmt(metrics.get("crack_spread_asof_date", metrics.get("oil_price_asof_date")))}
* Gasoline product supplied 4W change: {_million_barrels_per_day(metrics.get("gasoline_product_supplied_4w_change"), metrics.get("gasoline_product_supplied_units"))}
* Distillate product supplied 4W change: {_million_barrels_per_day(metrics.get("distillate_product_supplied_4w_change"), metrics.get("distillate_product_supplied_units"))}
* Jet fuel product supplied 4W change: {_million_barrels_per_day(metrics.get("jet_fuel_product_supplied_4w_change"), metrics.get("jet_fuel_product_supplied_units"))}
* Gasoline crack proxy: {_fmt(metrics.get("gasoline_crack_proxy"))}
* Diesel crack proxy: {_fmt(metrics.get("diesel_crack_proxy"))}
* Gasoline crack 20D change: {_fmt(metrics.get("gasoline_crack_20d_change"))}
* Diesel crack 20D change: {_fmt(metrics.get("diesel_crack_20d_change"))}
* Gasoline crack 20D MA: {_fmt(metrics.get("gasoline_crack_20d_ma"))}
* Diesel crack 20D MA: {_fmt(metrics.get("diesel_crack_20d_ma"))}
* Product demand signal: {metrics.get("product_demand_signal", "mixed_product_demand")}

## 5. 利率曲線與資金成本

* FRED rates as-of date: {_date_fmt(metrics.get("fred_rates_asof_date"))}
* Rates curve as-of date: {_date_fmt(metrics.get("rates_curve_asof_date"))}
* Fed Funds: {_fmt(metrics.get("fedfunds"), missing_label="missing")}
* SOFR: {_fmt(metrics.get("sofr"), missing_label="missing")}
* 3M: {_fmt(metrics.get("three_month"), missing_label="missing")}
* 1Y: {_fmt(metrics.get("one_year"), missing_label="missing")}
* 2Y: {_fmt(metrics.get("two_year"), missing_label="missing")}
* 5Y: {_fmt(metrics.get("five_year"), missing_label="missing")}
* 10Y: {_fmt(metrics.get("ten_year"), missing_label="missing")}
* 30Y: {_fmt(metrics.get("thirty_year"), missing_label="missing")}

Curve:
* 10Y-3M: {_fmt(metrics.get("ten_year_three_month_spread"))} (as-of {_spread_asof(metrics, "ten_year_three_month_spread")})
* 10Y-2Y: {_fmt(metrics.get("ten_year_two_year_spread"))} (as-of {_spread_asof(metrics, "ten_year_two_year_spread")})
* 5Y-2Y: {_fmt(metrics.get("five_year_two_year_spread"))} (as-of {_spread_asof(metrics, "five_year_two_year_spread")})
* 10Y-5Y: {_fmt(metrics.get("ten_year_five_year_spread"))} (as-of {_spread_asof(metrics, "ten_year_five_year_spread")})
* 30Y-10Y: {_fmt(metrics.get("thirty_year_ten_year_spread"))} (as-of {_spread_asof(metrics, "thirty_year_ten_year_spread")})

Official FRED spread reference:
* T10Y2Y: {_fmt(metrics.get("ten_year_two_year_spread_fred"))} (as-of {_date_fmt(metrics.get("ten_year_two_year_spread_fred_asof_date"))})
* T10Y3M: {_fmt(metrics.get("ten_year_three_month_spread_fred"))} (as-of {_date_fmt(metrics.get("ten_year_three_month_spread_fred_asof_date"))})

Belly dynamics:
* 2Y 20D change: {_fmt(metrics.get("two_year_change_20d"))}
* 5Y 20D change: {_fmt(metrics.get("five_year_change_20d"))}
* 10Y 20D change: {_fmt(metrics.get("ten_year_change_20d"))}
* 30Y 20D change: {_fmt(metrics.get("thirty_year_change_20d"))}
* belly_relative_move: {_fmt(metrics.get("belly_relative_move"))}

Carry:
* 2Y-SOFR: {_fmt(metrics.get("two_year_sofr_carry_proxy"))}
* 5Y-SOFR: {_fmt(metrics.get("five_year_sofr_carry_proxy"))}
* 10Y-SOFR: {_fmt(metrics.get("ten_year_sofr_carry_proxy"))}
* 30Y-SOFR: {_fmt(metrics.get("thirty_year_sofr_carry_proxy"))}

Funding:
* SOFR-Fed Funds: {_fmt(metrics.get("sofr_fedfunds_spread"))}
* 3M-Fed Funds: {_fmt(metrics.get("three_month_fedfunds_spread"))}

Rates signals:
* policy_rate_level: {metrics.get("policy_rate_level", "mixed")}
* funding_pressure_signal: {metrics.get("funding_pressure_signal", "mixed")}
* curve_slope_state: {metrics.get("curve_slope_state", "mixed")}
* belly_signal: {metrics.get("belly_signal", "mixed")}
* carry_signal: {metrics.get("carry_signal", "mixed")}
* roll_down_signal: {metrics.get("roll_down_signal", "mixed")}
* long_end_anchor_signal: {metrics.get("long_end_anchor_signal", "mixed")}
* rates_regime: {metrics.get("rates_regime", "mixed")}

## 6. 合成解讀

{build_interpretation(summary, metrics)}

## 7. Warnings

{warnings}
"""


def build_interpretation(summary: dict[str, Any], metrics: dict[str, Any]) -> str:
    macro_regime = summary.get("macro_regime", summary.get("regime", "neutral_mixed"))
    secondary_regime = summary.get("secondary_regime", "none")
    oil_signal = metrics.get("oil_momentum_signal", "unknown")
    inventory_signal = metrics.get("inventory_signal", "mixed")
    product_signal = metrics.get("product_demand_signal", metrics.get("crack_signal", "mixed_product_demand"))
    rates_regime = metrics.get("rates_regime", "mixed")
    carry_signal = metrics.get("carry_signal", "mixed")
    funding_signal = metrics.get("funding_pressure_signal", "mixed")
    crack_note = ""
    diesel_crack_level = metrics.get("diesel_crack_proxy", metrics.get("diesel_crack"))
    weak_product_signal = _is_weak_product_signal(product_signal)
    if product_signal == "demand_weakening" and _high_absolute_crack(diesel_crack_level):
        crack_note = "裂解價差絕對水位仍高，但近期動能轉弱，因此模型判定為 demand_weakening。"
    elif product_signal == "product_demand_softening_with_elevated_cracks":
        crack_note = "裂解價差絕對水位仍高，但三大成品供給量同步轉弱，因此模型判定為 product demand softening。"
    mixed_supply_demand_note = ""
    if inventory_signal == "inventory_tightening" and weak_product_signal:
        mixed_supply_demand_note = "庫存偏緊，但產品端需求動能轉弱，屬於供需混合訊號。"
    secondary_note = ""
    if secondary_regime == "tight_inventory_weak_products":
        secondary_note = (
            "目前不是單純供給緊縮，也不是單純需求轉弱，而是庫存偏緊、產品端動能轉弱的混合盤。"
            "這通常代表油價短線下方有庫存支撐，但若裂解價差持續走弱，中期仍要防需求端壓力。"
        )
    return (
        f"目前模型判定 macro regime 為 {macro_regime}，secondary regime 為 {secondary_regime}。"
        f"油價動能訊號是 {oil_signal}，因此價格本身還不能單獨說明是需求推動或供給推動；"
        f"庫存訊號為 {inventory_signal}，這代表現貨端是否支持油價，需要同時看原油、汽油、餾分油、煉廠開工率與出口。"
        f"成品需求訊號為 {product_signal}，若汽油、柴油與航煤供給量轉弱，通常代表終端需求動能降溫。"
        f"{crack_note}{mixed_supply_demand_note}{secondary_note}"
        f"利率端 regime 為 {rates_regime}，funding 訊號為 {funding_signal}，carry 訊號為 {carry_signal}。"
        "若 SOFR 高於中長債殖利率，金融機構借短買長的誘因有限，擴表意願會受到抑制；"
        "若 carry 修復，則代表債券配置與資產負債表擴張條件改善。"
        "綜合來看，油價與利率若同方向上行，多半是在交易通膨或成長共振；"
        "若油價有庫存支撐但產品端轉弱、利率仍壓抑 carry，則是成本與金融條件互相拉扯的盤面。"
    )


def report_warnings(summary: dict[str, Any], metrics: dict[str, Any]) -> list[str]:
    warnings = list(summary.get("warnings", []))
    if metrics.get("curve_state", "unknown") == "unknown":
        _append_unique(warnings, "Futures curve is unavailable in core FRED+EIA mode.")
    if metrics.get("yahoo_overlay", "OFF") == "OFF":
        _append_unique(warnings, "Yahoo overlay OFF")
    _append_unique(warnings, "Premium/manual data required for futures curve, OSP, freight, DUC, and global upstream CAPEX.")
    return warnings


def _append_unique(items: list[str], item: str) -> None:
    if item not in items:
        items.append(item)


def _fmt(value: Any, missing_label: str = "missing") -> str:
    try:
        if _is_missing(value):
            return missing_label
        return f"{float(value):,.2f}"
    except Exception:  # noqa: BLE001
        return missing_label


def _pct(value: Any) -> str:
    try:
        if _is_missing(value):
            return "missing"
        return f"{float(value) * 100:,.2f}%"
    except Exception:  # noqa: BLE001
        return "missing"


def _date_fmt(value: Any) -> str:
    if _is_missing(value):
        return "missing"
    try:
        text = str(value)
        if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
            return text[:10]
        return text
    except Exception:  # noqa: BLE001
        return "missing"


def _spread_asof(metrics: dict[str, Any], spread_name: str) -> str:
    return _date_fmt(metrics.get(f"{spread_name}_asof_date", metrics.get("rates_curve_asof_date")))


def _million_barrels(value: Any, units: Any = None) -> str:
    try:
        if _is_missing(value) or (not _is_missing(units) and not _is_thousand_barrels(units)):
            return "missing"
        return f"{float(value) / 1000:,.2f} million barrels"
    except Exception:  # noqa: BLE001
        return "missing"


def _million_barrels_per_day(value: Any, units: Any = None) -> str:
    try:
        if _is_missing(value) or (not _is_missing(units) and not _is_thousand_barrels_per_day(units)):
            return "missing"
        return f"{float(value) / 1000:,.2f} million barrels/day"
    except Exception:  # noqa: BLE001
        return "missing"


def _percent_level(value: Any) -> str:
    try:
        if _is_missing(value):
            return "missing"
        return f"{float(value):,.2f}%"
    except Exception:  # noqa: BLE001
        return "missing"


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == "" or value.strip().lower() in {"nan", "nat", "none", "missing"}
    try:
        return math.isnan(float(value))
    except Exception:  # noqa: BLE001
        return False


def _is_thousand_barrels(units: Any) -> bool:
    normalized = str(units).strip().upper()
    return normalized in {"MBBL", "THOUSAND BARRELS"}


def _is_thousand_barrels_per_day(units: Any) -> bool:
    normalized = str(units).strip().upper()
    return normalized in {"MBBL/D", "MBBL/DAY", "THOUSAND BARRELS PER DAY", "THOUSAND BARRELS/DAY"}


def _high_absolute_crack(value: Any) -> bool:
    try:
        return not _is_missing(value) and abs(float(value)) >= 25.0
    except Exception:  # noqa: BLE001
        return False


def _is_weak_product_signal(value: Any) -> bool:
    return value in {
        "demand_weakening",
        "broad_product_demand_softening",
        "product_demand_softening_with_elevated_cracks",
    }
