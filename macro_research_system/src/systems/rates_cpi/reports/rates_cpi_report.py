from __future__ import annotations

from pathlib import Path

from src.common.io import ensure_dir


def _fmt(value) -> str:
    return "missing" if value is None else f"{value:,.4f}"


def write_rates_cpi_report(summary: dict, output_dir: Path) -> Path:
    ensure_dir(output_dir)
    path = output_dir / f"rates_cpi_report_{summary['report_date'].replace('-', '')}.md"
    warnings = "\n".join(f"- {item}" for item in summary.get("warnings", [])) or "- none"
    mock_banner = "\n**MOCK DATA ONLY**\n" if summary.get("mock_mode") else ""
    content = f"""# Rates × CPI Monitor
{mock_banner}
Date: {summary['report_date']}

## Summary

- Rates regime: {summary['rates_regime']}
- Funding pressure signal: {summary['funding_pressure_signal']}
- Carry signal: {summary['carry_signal']}
- Curve signal: {summary['curve_signal']}
- CPI nowcast signal: {summary['cpi_nowcast_signal']}
- Data completeness score: {summary['data_completeness_score']}
- Regime confidence score: {summary['regime_confidence_score']}
- Real data ready: {summary['real_data_ready']}
- Data validation passed: {summary['data_validation_passed']}

## Rates

- Rates as-of: {summary.get('rates_asof_date') or 'missing'}
- Fed Funds: {_fmt(summary.get('fed_funds'))}
- SOFR: {_fmt(summary.get('sofr'))}
- 3M: {_fmt(summary.get('rate_3m'))}
- 1Y: {_fmt(summary.get('rate_1y'))}
- 2Y: {_fmt(summary.get('rate_2y'))}
- 5Y: {_fmt(summary.get('rate_5y'))}
- 10Y: {_fmt(summary.get('rate_10y'))}
- 30Y: {_fmt(summary.get('rate_30y'))}
- 10Y-3M: {_fmt(summary.get('spread_10y_3m'))}
- 10Y-2Y: {_fmt(summary.get('spread_10y_2y'))}
- 5Y-2Y: {_fmt(summary.get('spread_5y_2y'))}
- 30Y-10Y: {_fmt(summary.get('spread_30y_10y'))}
- SOFR minus Fed Funds: {_fmt(summary.get('sofr_fed_funds_spread'))}
- 3M minus Fed Funds: {_fmt(summary.get('three_month_fed_funds_spread'))}

## CPI Nowcast

- CPI as-of month: {summary.get('cpi_asof_month') or 'missing'}
- Headline MoM nowcast: {_fmt(summary.get('headline_cpi_mom_nowcast'))}
- Headline YoY nowcast: {_fmt(summary.get('headline_cpi_yoy_nowcast'))}
- Core MoM nowcast: {_fmt(summary.get('core_cpi_mom_nowcast'))}
- Core YoY nowcast: {_fmt(summary.get('core_cpi_yoy_nowcast'))}

## Warnings

{warnings}
"""
    path.write_text(content, encoding="utf-8")
    return path
