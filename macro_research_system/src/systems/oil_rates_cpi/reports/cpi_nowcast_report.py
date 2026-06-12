from __future__ import annotations


def render_cpi_nowcast_report(nowcast: dict) -> str:
    return f"""# CPI Nowcast

- Headline MoM: {nowcast.get('headline_cpi_mom_nowcast')}
- Core MoM: {nowcast.get('core_cpi_mom_nowcast')}
- Confidence: {nowcast.get('confidence_score')}

This is not official CPI.
"""
