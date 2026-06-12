from __future__ import annotations

from pathlib import Path

from src.common.io import ensure_dir


def write_oil_rates_cpi_report(summary: dict, output_dir: Path) -> Path:
    ensure_dir(output_dir)
    path = output_dir / f"oil_rates_cpi_report_{summary['report_date'].replace('-', '')}.md"
    warnings = "\n".join(f"- {item}" for item in summary.get("warnings", [])) or "- 無"
    content = f"""# Oil Rates CPI Monitor

日期：{summary['report_date']}

## 今日總結

- Macro regime: {summary['macro_regime']}
- Secondary regime: {summary['secondary_regime']}
- Data completeness score: {summary['data_completeness_score']}
- Regime confidence score: {summary['regime_confidence_score']}

## 原油與成品

- Oil as-of: {summary.get('oil_asof_date', 'missing')}
- WTI: {summary.get('wti')}
- Brent: {summary.get('brent')}
- Inventory signal: {summary['inventory_signal']}
- Product demand signal: {summary['product_demand_signal']}
- Crude exports: {summary.get('crude_exports')}

## 利率曲線

- Rates curve as-of: {summary.get('rates_curve_asof_date', 'missing')}
- 10Y-3M: {summary.get('ten_year_three_month_spread')}
- 10Y-2Y: {summary.get('ten_year_two_year_spread')}
- Funding pressure: {summary['funding_pressure_signal']}
- Carry signal: {summary['carry_signal']}
- Belly relative move: {summary.get('belly_relative_move')}

## CPI Nowcast

- CPI as-of: {summary.get('cpi_asof_date', 'missing')}
- CPI nowcast signal: {summary['cpi_nowcast_signal']}
- Headline CPI MoM nowcast: {summary['headline_cpi_mom_nowcast']}
- Core CPI MoM nowcast: {summary['core_cpi_mom_nowcast']}

## Warnings

{warnings}
"""
    path.write_text(content, encoding="utf-8")
    return path
