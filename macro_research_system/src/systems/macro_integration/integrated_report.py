from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from src.common.io import ensure_dir, write_json
from src.systems.macro_integration.regime_matrix import integrate_regimes
from src.systems.macro_integration.signal_adapter import load_system_summaries


def write_integration_chart(summary: dict, output_dir: Path) -> Path:
    ensure_dir(output_dir)
    path = output_dir / "integrated_risk_scores.png"
    labels = [
        "Equity Risk",
        "Bond Support",
        "Inflation Risk",
        "Deleveraging",
        "Commodity",
        "Tightening",
    ]
    values = [
        summary["equity_risk_score"],
        summary["bond_support_score"],
        summary["inflation_risk_score"],
        summary["deleveraging_risk_score"],
        summary["commodity_pressure_score"],
        summary["macro_tightening_score"],
    ]
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.bar(labels, values, color=["#d95f02", "#1b9e77", "#e7298a", "#7570b3", "#a6761d", "#666666"])
    ax.set_ylim(0, 100)
    ax.set_ylabel("Score")
    ax.set_title("Integrated Macro Risk Scores")
    ax.grid(True, axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def write_integrated_report(summary: dict, output_dir: Path) -> Path:
    ensure_dir(output_dir)
    path = output_dir / f"integrated_macro_report_{summary['report_date'].replace('-', '')}.md"
    warnings = "\n".join(f"- {item}" for item in summary.get("warnings", [])) or "- none"
    reasons = "\n".join(f"- {item}" for item in summary.get("integration_reasons", [])) or "- none"
    allocation = summary["asset_allocation_view"]
    content = f"""# Integrated Macro Monitor

日期：{summary['report_date']}

## 今日總結

- Final market state: {summary['final_market_state']}
- Equity risk score: {summary['equity_risk_score']}
- Bond support score: {summary['bond_support_score']}
- Inflation risk score: {summary['inflation_risk_score']}
- Deleveraging risk score: {summary['deleveraging_risk_score']}
- Commodity pressure score: {summary['commodity_pressure_score']}
- Macro tightening score: {summary['macro_tightening_score']}

## System A：TW Margin × Index Growth

- System ready: {summary['tw_margin_system_ready']}
- Final signal: {summary['tw_margin_final_signal']}
- Leverage cycle phase: {summary['tw_leverage_cycle_phase']}
- Risk level: {summary['tw_risk_level']}

## System B：Crude Oil Market

- System ready: {summary['oil_market_system_ready']}
- Oil regime: {summary['oil_regime']}
- Oil momentum signal: {summary['oil_momentum_signal']}
- Inventory signal: {summary['inventory_signal']}
- Product demand signal: {summary['product_demand_signal']}
- Supply signal: {summary['supply_signal']}
- Price war risk: {summary['price_war_risk']}
- Supply shock risk: {summary['supply_shock_risk']}
- Demand destruction risk: {summary['demand_destruction_risk']}

## System C：Rates × CPI

- System ready: {summary['rates_cpi_system_ready']}
- Rates regime: {summary['rates_regime']}
- Funding pressure signal: {summary['funding_pressure_signal']}
- Carry signal: {summary['carry_signal']}
- Curve signal: {summary['curve_signal']}
- CPI nowcast signal: {summary['cpi_nowcast_signal']}

## Cross-system interpretation

{reasons}

## Asset allocation view

- Equity: {allocation['equity']}
- High beta: {allocation['high_beta']}
- Bonds: {allocation['bonds']}
- Cash: {allocation['cash']}
- Commodities: {allocation['commodities']}
- Defensive assets: {allocation['defensive_assets']}

## Warnings

{warnings}
"""
    path.write_text(content, encoding="utf-8")
    return path


def run_integrated(data_root: Path) -> dict:
    tw, oil, rates, warnings = load_system_summaries(data_root)
    summary = integrate_regimes(tw, oil, rates)
    summary["warnings"].extend(warnings)
    base = ensure_dir(data_root / "integrated")
    write_json(base / "processed" / "integrated_macro_summary.json", summary)
    write_integrated_report(summary, base / "reports")
    write_integration_chart(summary, base / "charts")
    return summary
