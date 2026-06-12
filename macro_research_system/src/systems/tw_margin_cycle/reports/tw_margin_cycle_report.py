from __future__ import annotations

from pathlib import Path

from src.common.io import ensure_dir


def write_tw_margin_cycle_report(summary: dict, output_dir: Path) -> Path:
    ensure_dir(output_dir)
    path = output_dir / f"tw_margin_cycle_report_{summary['report_date'].replace('-', '')}.md"
    warnings = "\n".join(f"- {item}" for item in summary.get("warnings", [])) or "- 無"
    reasons = "\n".join(f"- {item}" for item in summary.get("final_signal_reasons", [])) or "- 無"
    content = f"""# TW Index-Margin Cycle Monitor

日期：{summary['report_date']}

## 摘要

- system: TW Margin × Index YoY Cycle Monitor
- raw_signal: {summary['raw_signal']}
- final_signal: {summary['final_signal']}
- leverage_cycle_phase: {summary['leverage_cycle_phase']}
- risk_level: {summary['risk_level']}
- market_extreme_warning: {summary['market_extreme_warning']}
- data_quality_warning: {summary['data_quality_warning']}

## 圖表

Main chart: data/tw_margin_cycle/charts/margin_index_original_style.png
Recent 5Y chart: data/tw_margin_cycle/charts/margin_index_original_style_recent5y.png

輔助圖表：

- secondary percent chart path: margin_index_yoy_percent_cycle.png
- secondary z-score chart path: margin_index_yoy_standardized_cycle.png
- detailed chart path: index_margin_cycle.png

本圖為原始觀察圖，使用同一個百分比尺度比較融資年增率、台股指數季增率與台股指數年增率。核心觀察是：當指數年增率與季增率已經大幅上升時，融資年增率是否也同步加速擴張。若三條線同時上行並處於高檔，代表市場可能進入融資追價或晚週期槓桿風險區。

## 指標

- Index close as-of {summary['data_end']}: {summary['index_close']:,.2f}
- Index YoY: {summary['index_yoy']:.4f}
- Index QoQ: {summary['index_qoq']:.4f}
- Margin balance: {summary['margin_balance_thousand_ntd']:,.0f}
- Margin balance percentile: {summary.get('margin_balance_percentile', 0.0):.2f}
- Margin ROC: {summary['margin_roc']:.4f}
- Margin ROC autocorr: {summary['margin_roc_autocorr']:.4f}
- Margin persistence score: {summary['margin_roc_persistence_score']:.4f}

## Signal Reasons

{reasons}

## Warnings

{warnings}
"""
    path.write_text(content, encoding="utf-8")
    return path
