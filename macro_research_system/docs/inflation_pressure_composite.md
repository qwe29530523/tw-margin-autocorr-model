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

## Food / Agriculture Component Status

The Food / Agriculture component now has a V1 data contract in `macro_research_system/config/food_inflation_series.yaml` and a design note at `macro_research_system/docs/food_inflation_pressure_design.md`.

V1 candidate signals are:

- `grain_pressure`
- `meat_protein_pressure`
- `food_cpi_trend`
- `food_ppi_pipeline_pressure`
- `food_commodity_momentum`

A Food signal backtest framework exists as a Supporting Research Layer. It evaluates candidate signals against forward food CPI, headline CPI, breakeven inflation, rates, and risk-asset drawdown targets when those target columns are available.

There is no Food production score yet. Composite weights remain gated by evidence, missing-data diagnostics, target availability, and test coverage.

Energy / Oil WTI curve real-data validation remains pending external vendor/API credentials. The Food component does not close or replace the Energy / Oil WTI curve work.

## Shelter / Housing Component Status

The Shelter / Housing component now has a V1 data contract in `macro_research_system/config/shelter_inflation_series.yaml` and a design note at `macro_research_system/docs/shelter_inflation_pressure_design.md`.

V1 candidate signals are:

- `shelter_cpi_trend`
- `rent_pressure`
- `oer_pressure`
- `home_price_momentum`
- `mortgage_rate_pressure`
- `housing_activity_pressure`
- `affordability_stress`
- `shelter_pipeline_pressure`

A Shelter signal backtest framework exists as a Supporting Research Layer. It evaluates candidate signals against forward shelter CPI, headline CPI, core CPI, breakeven inflation, rates, and risk-asset drawdown targets when those target columns are available.

Default Shelter backtest horizons include 1 month, 3 months, 6 months, and 12 months. The 6-month and 12-month windows are important because shelter inflation tends to lag home prices, rent contracts, and financing conditions.

There is no Shelter production score yet. Composite weights remain gated by evidence, missing-data diagnostics, target availability, and test coverage.

Energy / Oil WTI curve real-data validation remains pending external vendor/API credentials. The Shelter component does not close or replace the Energy / Oil WTI curve work.

## Services / Wage Component Status

The Services / Wage component now has a V1 data contract in `macro_research_system/config/services_wage_inflation_series.yaml` and a design note at `macro_research_system/docs/services_wage_inflation_pressure_design.md`.

V1 candidate signals are:

- `services_cpi_trend`
- `core_services_pressure`
- `supercore_services_proxy`
- `wage_growth_pressure`
- `labor_cost_pressure`
- `labor_market_tightness`
- `quits_pressure`
- `payroll_momentum`
- `claims_stress_inverse`
- `services_wage_pipeline_pressure`

A Services / Wage signal backtest framework exists as a Supporting Research Layer. It evaluates candidate signals against forward services CPI, core CPI, headline CPI, breakeven inflation, rates, and risk-asset drawdown targets when those target columns are available.

Default Services / Wage backtest horizons include 1 month, 3 months, 6 months, and 12 months. The 3-month, 6-month, and 12-month windows are more important than the 1-month window because services and wage inflation tend to be sticky and lagged.

There is no Services / Wage production score yet. Composite weights remain gated by evidence, missing-data diagnostics, target availability, and test coverage.

Energy / Oil WTI curve real-data validation remains pending external vendor/API credentials. The Services / Wage component does not close or replace the Energy / Oil WTI curve work.
