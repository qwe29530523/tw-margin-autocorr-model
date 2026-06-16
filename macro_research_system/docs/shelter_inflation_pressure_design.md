# Shelter / Housing Inflation Pressure Subsystem V1

Shelter / Housing Inflation Pressure Subsystem V1 is the Shelter / Housing component of the upper-level Inflation Pressure Composite.

It is not a full inflation score. V1 does not create or publish a production score, composite score, trading signal, or risk gate. Its purpose is to define a clean subsystem boundary, initial official data contract, transparent processor signals, and a backtest evidence layer.

## Source Policy

Preferred V1 sources are FRED and BLS.

FHFA and Census can be added later as official extensions for house prices, housing starts, permits, supply, and sales activity. Yahoo or other unofficial sources are not allowed as production sources. If an unofficial source is ever added, it must be marked research-only and cannot feed production scoring without a separate validation gate.

Missing data must not crash the pipeline. Missing inputs should be represented as NaN, missing ratios should be measured explicitly, and insufficient data must keep any future backtest result unusable for score.

## Candidate Data Groups

- `shelter_cpi`
- `rent_cpi`
- `owners_equivalent_rent`
- `home_price_index`
- `mortgage_rate`
- `housing_starts`
- `building_permits`
- `home_sales`
- `affordability_proxy`
- `vacancy_or_supply_proxy`

## Processor Output Contract

The V1 processor is exposed by:

```text
src.systems.shelter_inflation.processors.shelter_inflation_engine.build_shelter_inflation_engine
```

The V1 output schema is:

```text
date
shelter_cpi
shelter_cpi_sa
rent_cpi
owners_equivalent_rent
mortgage_rate_30y
mortgage_rate_15y
case_shiller_home_price
fhfa_home_price
housing_starts
building_permits
new_home_sales
shelter_cpi_1m_chg
shelter_cpi_3m_chg
rent_cpi_1m_chg
rent_cpi_3m_chg
oer_1m_chg
oer_3m_chg
home_price_3m_roc
mortgage_rate_3m_chg
housing_starts_3m_roc
building_permits_3m_roc
shelter_cpi_trend
rent_pressure
oer_pressure
home_price_momentum
mortgage_rate_pressure
housing_activity_pressure
affordability_stress
shelter_pipeline_pressure
source_confidence
missing_data_ratio
source_mode
```

Candidate signals:

- `shelter_cpi_trend`
- `rent_pressure`
- `oer_pressure`
- `home_price_momentum`
- `mortgage_rate_pressure`
- `housing_activity_pressure`
- `affordability_stress`
- `shelter_pipeline_pressure`

`source_confidence` is a data-quality diagnostic, not a directional production signal.

## Backtest Summary Contract

The V1 backtest layer is exposed by:

```text
src.systems.shelter_inflation.backtests.shelter_signal_backtest.run_shelter_signal_backtest
```

It evaluates candidate signals against targets such as:

- `shelter_cpi_forward_change`
- `headline_cpi_forward_change`
- `core_cpi_forward_change`
- `breakeven_inflation_forward_change`
- `rates_forward_change`
- `risk_asset_proxy_forward_drawdown`, if an already validated research-only target is available

Default horizons are 1, 3, 6, and 12 months. Shelter and OER have long lag structures, so the 6-month and 12-month horizons are especially important because shelter inflation lags home prices, rent contracts, and financing conditions.

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

`usable_for_score` is evidence-only. It is not a production weighting decision and does not create a production score. V1 uses a conservative monthly sample gate; diagnostic-only fields such as `source_confidence` stay unusable for directional scoring.

Backtest output should stay in ignored data paths and must not create production score JSON.

## Current Boundaries

V1 creates the package boundary, series config, design documentation, processor, and backtest framework. It does not implement real-data fetchers, data writes, charts, macro integration changes, production scoring, or composite scoring.

Energy / Oil WTI curve real-data validation remains pending external vendor/API credentials under the Energy / Oil subsystem. The Shelter / Housing subsystem does not close or replace that work. Yahoo and `CL=F` must not be used as WTI M1/M2/M3 futures curve sources.
