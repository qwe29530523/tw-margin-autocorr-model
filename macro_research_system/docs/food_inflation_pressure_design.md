# Food Inflation Pressure Subsystem V1

Food Inflation Pressure Subsystem V1 is the Food / Agriculture component of the upper-level Inflation Pressure Composite.

It is not a full inflation score, and V1 does not create or publish any production score. Its purpose is to define the food data contract, transparent candidate signals, and backtest evidence layer that can later inform a composite design.

## Source Policy

Preferred V1 sources are FRED and BLS.

Yahoo is not allowed as a production source. Any future Yahoo or market-data overlay must be marked research-only and must not be used as production inflation evidence without a separate validation gate.

Missing data must not crash the pipeline. Missing inputs are represented as NaN, missing ratios are measured explicitly, and insufficient data must keep `usable_for_score=false`.

## Processor Output Contract

The processor is exposed by:

```text
src.systems.food_inflation.processors.food_inflation_engine.build_food_inflation_engine
```

The V1 output schema is:

```text
date
food_cpi
food_at_home_cpi
food_ppi
wheat_price
corn_price
soybean_price
rice_price
beef_price
meat_ppi
food_cpi_1m_chg
food_cpi_3m_chg
food_ppi_1m_chg
food_ppi_3m_chg
wheat_3m_roc
corn_3m_roc
soybean_3m_roc
grain_pressure
meat_protein_pressure
food_cpi_trend
food_ppi_pipeline_pressure
food_commodity_momentum
source_confidence
missing_data_ratio
source_mode
```

Candidate signals:

- `grain_pressure`
- `meat_protein_pressure`
- `food_cpi_trend`
- `food_ppi_pipeline_pressure`
- `food_commodity_momentum`

`source_confidence` is a data-quality diagnostic, not a directional production signal.

## Backtest Summary Contract

The backtest layer is exposed by:

```text
src.systems.food_inflation.backtests.food_signal_backtest.run_food_signal_backtest
```

Each summary row contains:

```text
signal_name
target_name
horizon_months
sample_count
hit_rate
information_coefficient
missing_data_ratio
target_missing_data_ratio
suggested_direction
suggested_weight_range
usable_for_score
unusable_reason
source_columns
feature_role
```

`usable_for_score` is evidence-only. It is not a production weighting decision and does not create a production score. V1 uses a conservative minimum sample gate for monthly data; diagnostic-only features such as `source_confidence` stay unusable for directional scoring.

## Current Boundaries

Food subsystem will later include fetcher modules and real-data runner wiring. V1 currently provides the processor and backtest framework only.

Energy / Oil WTI curve real-data validation remains pending under the Energy / Oil subsystem. That work is not closed by this Food subsystem. When vendor credentials arrive, resume the WTI curve workflow with `WTI_CURVE_API_URL`, `WTI_CURVE_API_KEY`, response sample, field mapping, individual CL contract-month daily settlements, and M1/M2/M3 ladder validation.
