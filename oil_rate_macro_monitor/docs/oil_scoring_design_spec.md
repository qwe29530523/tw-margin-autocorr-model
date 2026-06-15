# Oil / Energy Inflation Scoring Design Spec

This document is a scoring design spec for the Energy / Oil Inflation Pressure Subsystem. It is not a production score implementation, not a formal trading signal, and not a replacement for the Inflation Pressure Composite System.

Production scoring must wait until upstream data coverage and backtest validation are complete. No production score, output JSON, trading signal, or integration-layer behavior is created by this spec.

## Score Name

Proposed future score:

```text
energy_oil_inflation_pressure_score
```

Positioning:

- Represents only the Energy / Oil component.
- Must not be used as the full inflation pressure score.
- Must not replace the upper-level Inflation Pressure Composite System.
- Can become one input to the composite only after production readiness gates pass.

## Phase 2B Candidate Set

Directional signal candidates:

- `oil_price_momentum`
- `oil_price_regime`
- `physical_tightness`
- `product_inventory_pressure`
- `inflation_rates_transmission`

Confidence modifier:

- `source_confidence`

Excluded for now:

- `wti_curve_state`: no formal WTI futures curve upstream; current missing ratio is `1.0`.
- `breakeven_inflation_forward_change`: unavailable target.
- `risk_asset_proxy_forward_return`: unavailable target.

## Current Backtest Evidence

Phase 2A established that `physical_tightness` and `product_inventory_pressure` were originally duplicate-like. Their derivations were separated in the backtest layer.

Current duplicate diagnostics:

| Pair | Raw Values Equal | Correlation | Duplicate Of |
| --- | --- | ---: | --- |
| `physical_tightness` vs `product_inventory_pressure` | `false` | `0.1262` | `None` |

Current interpretation:

- `physical_tightness` has enough observations to remain a candidate, but evidence is weak to moderate. It should not receive high production weight without more validation.
- `product_inventory_pressure` is weaker than `physical_tightness`. It can remain a low-weight candidate only if duplicate diagnostics continue to pass.
- `source_confidence` is a confidence modifier only. It should not be treated as a directional inflation pressure signal.
- `wti_curve_state` remains unusable until a formal futures curve upstream exists.

## Evidence Strength Rules

| Evidence Level | Requirements |
| --- | --- |
| Strong | Sample count is sufficient; hit rate is clearly above `0.55` or below `0.45`; IC is stable and directionally consistent; multiple horizons and targets agree. |
| Moderate | Sample count is sufficient; hit rate is around `0.52-0.55`; IC is weak but broadly directionally consistent. |
| Weak | Hit rate is near `0.50`; IC is near zero or directionally unstable; use only as low-weight support. |
| Unusable | Missing ratio is too high; sample count is `0`; `duplicate_of` is not `None`; target is unavailable; upstream data is missing. |

Evidence classification is research guidance only. It does not create production score weights.

## Weight Policy

Future production implementation may use weight ranges, not fixed weights:

| Component | Directional Role | Design Weight Range | Current Caveat |
| --- | --- | ---: | --- |
| `oil_price_momentum` | Oil price direction | `0-0.05` | Candidate only. |
| `oil_price_regime` | Oil regime label | `0-0.05` | Candidate only. |
| `physical_tightness` | Full physical oil market tightness | `0-0.10` | Evidence is weak/moderate. |
| `product_inventory_pressure` | Product-side pressure | `0-0.05` | Weaker than `physical_tightness`; avoid double-counting. |
| `inflation_rates_transmission` | Oil to rates/inflation transmission | `0-0.10` | Candidate only. |
| `source_confidence` | Confidence modifier | Directional weight: none | Use as multiplier or confidence label only. |

Policy rules:

- If any signal is marked `duplicate_of`, it cannot receive independent directional weight.
- If source confidence is low, reduce score confidence, not the directional score itself.
- If WTI curve, breakeven, and risk asset targets remain unavailable, this design must not be upgraded to production.
- Weight ranges are design boundaries, not hard-coded production weights.

## Future Production Score Schema

Example schema only:

```json
{
  "energy_oil_inflation_pressure_score": null,
  "score_status": "DESIGN_ONLY",
  "score_regime": null,
  "directional_components": {},
  "confidence_modifier": {},
  "excluded_components": {},
  "evidence_version": "phase_2b_design_spec",
  "production_ready": false
}
```

This schema must not be emitted as production output until the readiness gates below pass.

## Production Readiness Gate

Before any production score goes live, the system needs:

1. WTI futures curve upstream.
2. Breakeven inflation target.
3. Risk asset proxy target.
4. Duplicate diagnostics passing for all directional signals.
5. Every directional signal reporting sample count, hit rate, and IC.
6. Source confidence modifier independent from directional scoring.
7. `pytest` passing.
8. `output/`, `exports/`, debug files, charts, and processed data not tracked by Git.
9. Integration layer reading only published score output and not recomputing subsystem internals.

## Non-Goals

- No production score implementation.
- No trading signal.
- No buy/sell, risk-on/risk-off, or sizing rule.
- No hard-coded production weights.
- No fabricated WTI curve, breakeven, or risk asset target data.
