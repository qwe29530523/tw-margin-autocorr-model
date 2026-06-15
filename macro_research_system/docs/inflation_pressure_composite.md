# Inflation Pressure Composite System

This document defines the upper-level inflation pressure architecture.

`oil_rate_macro_monitor` is not a full inflation index. It is the **Energy / Oil Inflation Pressure Subsystem** only. Its oil score can be used as one component of a broader inflation pressure composite, but it must not be used directly as a global inflation pressure score.

## Required Components

A production Inflation Pressure Composite System should validate at least these components:

1. Energy / Oil
2. Food / Agriculture
3. Shelter / Housing
4. Services / Wage
5. Goods / Supply Chain
6. FX / Import Inflation
7. Inflation Expectations / Rates Transmission

## Scoring Rule

The Energy / Oil score can only represent energy inflation pressure. It cannot represent food, shelter, wage, goods, FX, or expectations channels.

Production inflation scoring must not be created from the oil subsystem alone. Each component needs its own data contract, backtest evidence, validation, missing-data handling, and suggested weight range before a composite production score is introduced.

The Energy / Oil component has a Phase 2B design-only spec at `oil_rate_macro_monitor/docs/oil_scoring_design_spec.md`. That spec does not create production scoring and cannot be promoted into the composite until WTI curve, breakeven, risk asset targets, duplicate diagnostics, and pytest gates pass.

## Current Status

The current oil backtest layer is a Supporting Research Layer. It can evaluate whether oil-related signals deserve future production use, but it does not create production score weights and does not change any production macro decision logic.
