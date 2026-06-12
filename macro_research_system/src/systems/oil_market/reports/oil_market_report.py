from __future__ import annotations

from pathlib import Path

from src.common.io import ensure_dir
from src.systems.oil_market.processors.oil_price_engine import pct_text


def _missing(value) -> bool:
    if value is None:
        return True
    try:
        return bool(value != value)
    except TypeError:
        return True


def _fmt(value, digits: int = 2) -> str:
    if _missing(value):
        return "missing"
    return f"{value:,.{digits}f}"


def _fmt_million_barrels(value) -> str:
    if _missing(value):
        return "missing"
    return f"{value / 1000:,.2f} million barrels"


def _fmt_million_bpd(value) -> str:
    if _missing(value):
        return "missing"
    return f"{value / 1000:,.2f} million barrels/day"


def _research_note(summary: dict) -> str:
    if not summary.get("real_data_ready", False):
        return (
            "MOCK DATA ONLY — NOT FOR MARKET INTERPRETATION。"
            "目前 FRED 或 EIA 資料未通過 real-data validation，或系統仍在 mock/fallback mode。"
            "因此本報告只用於檢查資料管線、欄位 schema、圖表輸出與 warning 機制，不輸出正式油市研究判斷。"
            "請先確認 FRED_API_KEY、EIA_API_KEY、MOCK_MODE=false，以及資料序列通過 date frequency、非線性 ramp、"
            "非 sawtooth / square-wave fixture 的驗證後，再使用 regime 解讀。"
        )
    regime = summary.get("oil_regime", "neutral_mixed")
    inventory = summary.get("inventory_signal", "neutral")
    demand = summary.get("product_demand_signal", "neutral")
    crack = summary.get("crack_signal", "neutral")
    supply = summary.get("supply_signal", "neutral")
    momentum = summary.get("oil_momentum_signal", "neutral")
    return (
        f"目前油市 regime 為 {regime}。油價動能訊號為 {momentum}，代表價格本身尚未單獨構成完整判斷，"
        f"需要搭配庫存、成品需求與供給端一起看。庫存訊號為 {inventory}；若庫存偏緊，現貨端通常仍有支撐，"
        f"但若同時看到成品需求訊號為 {demand}，就表示油價不是單純需求擴張行情，而可能是供需混合。"
        f"裂解價差訊號為 {crack}，可用來判斷煉油利潤與產品端需求是否仍有韌性。供給訊號為 {supply}，"
        "若美國產量與出口同步上升，代表供給正在補上，會削弱庫存偏緊對油價的支撐。"
        "整體而言，本報告將油價、庫存、產品需求、裂解價差、煉廠與供給分開判讀，再合成 regime。"
    )


def write_oil_market_report(summary: dict, output_dir: Path) -> Path:
    ensure_dir(output_dir)
    path = output_dir / f"oil_market_report_{summary['report_date'].replace('-', '')}.md"
    warnings = "\n".join(f"- {item}" for item in summary.get("warnings", [])) or "- 無"
    validation_warnings = "\n".join(f"- {item}" for item in summary.get("data_validation_warnings", [])) or "- 無"
    banner = "\n\n**MOCK DATA ONLY — NOT FOR MARKET INTERPRETATION**\n" if not summary.get("real_data_ready", False) else ""
    interpretation_status = (
        "- Formal market interpretation: disabled\n\n" if not summary.get("real_data_ready", False) else ""
    )
    content = f"""# Crude Oil Market Monitor

{banner}

日期：{summary['report_date']}

## 1. 今日總結

- Oil regime: {summary['oil_regime']}
- Regime confidence: {summary['regime_confidence_score']}
- Oil momentum signal: {summary['oil_momentum_signal']}
- Inventory signal: {summary['inventory_signal']}
- Product demand signal: {summary['product_demand_signal']}
- Crack signal: {summary['crack_signal']}
- Refinery signal: {summary['refinery_signal']}
- Supply signal: {summary['supply_signal']}
- Price war risk: {summary['price_war_risk']}
- Supply shock risk: {summary['supply_shock_risk']}
- Demand destruction risk: {summary['demand_destruction_risk']}
- Data source mode: {summary.get('data_source_mode')}
- FRED real data: {summary.get('fred_real_data')}
- EIA real data: {summary.get('eia_real_data')}
- Real data ready: {summary.get('real_data_ready')}
- Data validation passed: {summary.get('data_validation_passed')}
- Oil price as-of date: {summary.get('oil_asof_date') or 'missing'}
- EIA inventory as-of date: {summary.get('inventory_asof_date') or 'missing'}
- Product demand as-of date: {summary.get('product_demand_asof_date') or 'missing'}

## 2. 油價

- WTI: {_fmt(summary['wti'])}
- Brent: {_fmt(summary['brent'])}
- Brent-WTI spread: {_fmt(summary['brent_wti_spread'])}
- WTI 5D / 20D / 60D: {pct_text(summary['wti_return_5d'])} / {pct_text(summary['wti_return_20d'])} / {pct_text(summary['wti_return_60d'])}
- Brent 5D / 20D / 60D: {pct_text(summary['brent_return_5d'])} / {pct_text(summary['brent_return_20d'])} / {pct_text(summary['brent_return_60d'])}

## 3. 庫存

- crude inventory 4W change: {_fmt_million_barrels(summary['crude_inventory_4w_change'])}
- gasoline inventory 4W change: {_fmt_million_barrels(summary['gasoline_inventory_4w_change'])}
- distillate inventory 4W change: {_fmt_million_barrels(summary['distillate_inventory_4w_change'])}
- total inventory proxy 4W change: {_fmt_million_barrels(summary['total_inventory_proxy_4w_change'])}

## 4. 成品需求

- gasoline product supplied 4W change: {_fmt_million_bpd(summary['gasoline_product_supplied_4w_change'])}
- distillate product supplied 4W change: {_fmt_million_bpd(summary['distillate_product_supplied_4w_change'])}
- jet fuel product supplied 4W change: {_fmt_million_bpd(summary['jet_fuel_product_supplied_4w_change'])}
- product demand signal: {summary['product_demand_signal']}

## 5. 裂解價差

- gasoline crack proxy: {_fmt(summary['gasoline_crack_proxy'])}
- diesel crack proxy: {_fmt(summary['diesel_crack_proxy'])}
- gasoline crack 20D change: {_fmt(summary['gasoline_crack_20d_change'])}
- diesel crack 20D change: {_fmt(summary['diesel_crack_20d_change'])}
- crack signal: {summary['crack_signal']}

## 6. 煉廠與供給

- refinery utilization: {_fmt(summary['refinery_utilization'])}
- refinery crude inputs: {_fmt_million_bpd(summary['refinery_crude_inputs'])}
- crude production: {_fmt_million_bpd(summary['crude_production'])}
- crude exports: {_fmt_million_bpd(summary['crude_exports'])}
- refinery signal: {summary['refinery_signal']}
- supply signal: {summary['supply_signal']}

## 7. 原油市場解讀

{interpretation_status}
{_research_note(summary)}

## 8. Warnings

### Data Validation

{validation_warnings}

### Runtime

{warnings}
"""
    path.write_text(content, encoding="utf-8")
    return path
