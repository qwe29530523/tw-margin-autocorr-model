# Macro Research System

This project is sealed at the A/B/C/D system-contract layer. New systems, schedulers, dashboards, alert layers, deeper System D backtests, and confidence-model changes should be added only after preserving the contracts documented here.

## Architecture

### System A: `tw_margin_cycle`

**TW Margin × Index Growth**

- Uses Taiwan margin balance change, index year-over-year growth, and index quarter-over-quarter growth.
- Produces the Taiwan leverage-cycle signal, leverage phase, and risk level.
- Output summary: `data/tw_margin_cycle/processed/tw_margin_cycle_summary.json`

### System B: `oil_market`

**Crude Oil Market Monitor**

- Pure crude oil system.
- Uses FRED + EIA only.
- Does not include rates, CPI, funding, carry, or yield curve inputs.
- Output summary: `data/oil_market/processed/oil_market_summary.json`

### System C: `rates_cpi`

**Rates × CPI Monitor**

- Pure rates and CPI system.
- Uses FRED + BLS only.
- Does not include oil, WTI, Brent, inventory, refinery, or crack spread inputs.
- Output summary: `data/rates_cpi/processed/rates_cpi_summary.json`

### System D: `macro_integration`

**Integrated Macro Monitor**

- Reads only System A/B/C summary JSON files.
- Does not directly read raw data.
- Does not read `data/oil_rates_cpi/processed/oil_rates_cpi_summary.json`.
- Output summary: `data/integrated/processed/integrated_macro_summary.json`

### Legacy: `oil_rates_cpi`

- Legacy mixed macro system.
- Preserved for backward compatibility and tests.
- Not used as formal integration-layer input.

## CLI

Run from `macro_research_system/`:

```bash
python -m src.main run-tw-margin
python -m src.main run-oil-market
python -m src.main run-rates-cpi
python -m src.main run-integrated
python -m src.main run-all
python -m src.main backtest-oil-market --start 2018-01-01 --end 2026-06-08
python -m src.main backtest-cpi --start 2018-01 --end 2026-05
```

`run-all` order:

```text
run-tw-margin
run-oil-market
run-rates-cpi
run-integrated
```

Legacy CLI remains available:

```bash
python -m src.main run-oil-rates-cpi
```

## Environment

Copy `.env.example` to `.env` locally and fill in only local secrets:

```text
FRED_API_KEY=
EIA_API_KEY=
BLS_API_KEY=
MOCK_MODE=true
USE_YAHOO=false
```

Rules:

- Real API keys must never be committed.
- `.env` must stay ignored by git.
- If a key is missing, the affected fetcher falls back to mock data and does not crash.
- Mock-mode reports and charts must clearly show `MOCK DATA ONLY`.

## Output Contracts

See [docs/output_contracts.md](docs/output_contracts.md).

## Verification

See [docs/verification.md](docs/verification.md).

## Separation Rules

- `oil_market` must not include CPI, rates, funding, carry, or yield curve logic.
- `rates_cpi` must not include oil, WTI, Brent, inventory, refinery, or crack spread logic.
- `macro_integration` reads only A/B/C summary JSON files.
- `macro_integration` must not read legacy `oil_rates_cpi_summary.json`.
- `oil_rates_cpi` stays available as legacy; do not delete it or break its existing tests.

## External Integration Layer

`macro_research_system/src/integrations/` is a thin upper-level adapter layer for independently deployed systems. It does not move folders, merge models, copy local data, or recompute any subsystem output.

### Independent Systems

- Taiwan Local Liquidity System
  - Root: `TW_MARGIN_SYSTEM_ROOT`
  - Primary output: `output/signal_summary.json`
  - Fallback when `TW_MARGIN_SYSTEM_ROOT` is unset: repo root `output/signal_summary.json`
  - Adapter: `tw_margin_adapter.py`

- Global Oil / Inflation Pressure System
  - Root: `OIL_INFLATION_SYSTEM_ROOT`
  - Reads the latest report or processed data under that root.
  - Fallback when `OIL_INFLATION_SYSTEM_ROOT` is unset: repo root `oil_rate_macro_monitor/`
  - Adapter: `oil_rate_adapter.py`
  - Formal decision architecture has exactly five layers:
    - Oil Price & WTI Curve
    - Physical Tightness
    - Product Inventory Pressure
    - Oil → Inflation / Rates Transmission
    - Final Oil-Rate Macro Regime
  - Fetchers, processors, validation, reports, charts, and tests are Supporting Implementation Layers only.

The Taiwan margin liquidity system and the oil + inflation system are separate systems. Neither adapter depends on the other system's paths. The integration layer reads published outputs from each system; it does not treat data validation, reports, charts, fetchers, processors, or tests as separate macro decision systems.

### Aggregated Summary

`macro_system_aggregator.py` writes:

```text
macro_research_system/data/outputs/macro_system_summary.json
```

The output schema is:

- `taiwan_local_liquidity`
- `global_oil_inflation_pressure`
- `final_macro_risk_gate`

If either source is unavailable, its adapter returns `status="MISSING"` and the aggregator still writes a summary. This output JSON is ignored by git.
