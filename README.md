# Jeff Macro System

Jeff Macro System is a macro regime diagnosis system. It organizes macro, inflation, commodity, positioning, and market-structure data into structured outputs that can be tracked, compared, and connected to a future Macro Regime Kernel.

This is not a single trading signal system. It is not a buy / sell engine.

## Current Complete Repository

Current complete repo:

`qwe29530523/tw-margin-autocorr-model`

Legacy / early prototype repo:

`qwe29530523/liquidity-market-analysis`

`liquidity-market-analysis` was an early prototype. The current complete version is maintained in `tw-margin-autocorr-model`.

## Current Status

Oil Macro Core v1 is complete and pushed to GitHub.

Latest completed commit:

`528301b Add oil macro summary adapter`

Validation:

```bash
python -m pytest
```

Current result:

```text
220 passed
```

## What This Model Is For

This system is used to diagnose macro regimes, especially commodity and inflation pressure conditions.

Oil Macro Core v1 is the first completed domain module. It helps evaluate whether the oil market is showing:

- inflation pressure
- physical tightness
- refined product margin support
- crowded short / positioning squeeze risk
- disinflation or demand weakness
- missing-data or vendor-source blockers

The output is intended to be one input into a broader macro decision framework, not a standalone trading signal.

## Oil Macro Core V1 Information Layers

### 1. Oil Price And Inflation Pressure

Includes:

- WTI price
- Brent price
- WTI / Brent ROC
- headline CPI
- core CPI
- energy CPI
- gasoline CPI
- food CPI
- shelter CPI
- breakeven inflation
- nominal yield
- real yield
- `oil_rate_mix`

Purpose:

This layer diagnoses whether oil prices are forming inflation pressure, or whether the setup is closer to disinflation / growth scare.

### 2. Physical Tightness

Includes:

- crude inventory
- gasoline inventory
- distillate inventory
- refinery utilization
- crude production
- crude exports
- SPR inventory
- `product_inventory_pressure`
- `oil_physical_tightness`

Purpose:

This layer diagnoses whether the physical crude and refined-product system is tight, loose, or mixed.

### 3. Crack Spread Research Proxy

Includes:

- `CL=F`
- `RB=F`
- `HO=F`
- `gasoline_crack_research_proxy`
- `distillate_crack_research_proxy`
- `crack_321_research_proxy`

Purpose:

This layer uses free yfinance proxies to observe refined product margin direction.

Caveat:

yfinance crack spread data is a research-only proxy. It is not an official CME / Barchart / Nasdaq verified crack spread.

### 4. CFTC Oil Positioning Diagnostics

Includes:

- Managed Money long
- Managed Money short
- Managed Money net
- Managed Money net percent of open interest
- Managed Money short percentile
- Managed Money net percentile
- 1w change
- 7w cumulative change
- `oil_positioning_state`
- `oil_squeeze_risk`

Purpose:

This layer diagnoses whether crude oil short positioning is crowded, and whether there is short-covering / squeeze candidate risk.

Caveat:

CFTC positioning is diagnostics only. It is not a final oil trading signal.

### 5. Futures Curve Blocker Metadata

Includes:

- `wti_m1_m2_m3_curve`
- `BLOCKED_VENDOR_NOT_CONFIGURED`

Purpose:

This layer explicitly marks that the current WTI M1/M2/M3 futures curve has not yet been connected to a verified vendor source.

Caveat:

FRED / BLS / EIA / Census / MetalPriceAPI / yfinance cannot replace CME CL futures curve data.

## Oil Macro Summary Adapter

Oil Macro Summary Adapter aggregates the above layers into a structured summary object for future Macro Regime Kernel consumption.

Summary output keys:

- `module_name`
- `as_of_date`
- `data_status`
- `oil_rate_mix`
- `oil_physical_tightness`
- `product_inventory_pressure`
- `crack_spread_proxy_status`
- `gasoline_crack_research_proxy_trend`
- `distillate_crack_research_proxy_trend`
- `crack_321_research_proxy_trend`
- `oil_positioning_state`
- `oil_squeeze_risk`
- `wti_curve_status`
- `primary_oil_macro_regime`
- `confidence`
- `risk_level`
- `drivers`
- `warning_flags`
- `next_watch_items`
- `data_caveats`

Allowed `primary_oil_macro_regime` labels:

- `PHYSICAL_TIGHT_WITH_RESEARCH_PROXY_SUPPORT`
- `PHYSICAL_TIGHT_BUT_CURVE_BLOCKED`
- `RESEARCH_PROXY_POSITIONING_SQUEEZE_CANDIDATE`
- `DISINFLATION_OR_DEMAND_WEAKNESS`
- `MIXED_OIL_MACRO_REGIME`
- `MISSING_OIL_MACRO_DATA`

## What This System Does Not Do

- It does not create `production_score`.
- It does not create `composite_score`.
- It does not create `final_trading_signal`.
- It does not create `buy_signal` or `sell_signal`.
- It does not treat yfinance as an official / verified source.
- It does not treat CFTC positioning as a final oil signal.
- It does not close the WTI M1/M2/M3 futures curve blocker.
- It does not replace CME / Barchart / Nasdaq verified futures data.

## Main Files

- `macro_research_system/config/domain_input_mappings.yaml`
- `macro_research_system/config/energy_benchmark_research_sources.yaml`
- `macro_research_system/config/cftc_positioning_sources.yaml`
- `macro_research_system/src/systems/common/domain_input_builder.py`
- `macro_research_system/src/systems/oil_market/fetch_yfinance_energy_research.py`
- `macro_research_system/src/systems/oil_market/calculate_crack_spread_research.py`
- `macro_research_system/src/systems/oil_market/calculate_cftc_oil_positioning.py`
- `macro_research_system/src/systems/oil_market/build_oil_macro_summary.py`
- `macro_research_system/docs/inflation_pressure_composite.md`

## Testing

Run:

```bash
python -m pytest
```

Current result:

```text
220 passed
```

## Next Planned Phase

Phase 2F: Macro Regime Kernel input contract

Purpose:

Define a standard interface for all domain modules to feed the future Macro Regime Kernel.

Expected common fields:

- `module_name`
- `as_of_date`
- `data_status`
- `primary_regime`
- `secondary_regime`
- `confidence`
- `risk_level`
- `drivers`
- `warning_flags`
- `next_watch_items`
- `data_caveats`
