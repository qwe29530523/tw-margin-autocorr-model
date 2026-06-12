# Verification

Last sealed command set: 2026-06-11.

Run all commands from `macro_research_system/`.

## Current Verification Commands

```bash
python -m src.main run-tw-margin
python -m src.main run-oil-market
python -m src.main run-rates-cpi
python -m src.main run-integrated
python -m src.main run-all
python -m src.main backtest-oil-market --start 2018-01-01 --end 2026-06-08
python -m src.main backtest-cpi --start 2018-01 --end 2026-05
pytest
```

## Expected Status

- `python -m src.main run-tw-margin`: passed
- `python -m src.main run-oil-market`: passed
- `python -m src.main run-rates-cpi`: passed
- `python -m src.main run-integrated`: passed
- `python -m src.main run-all`: passed
- `python -m src.main backtest-oil-market --start 2018-01-01 --end 2026-06-08`: passed
- `python -m src.main backtest-cpi --start 2018-01 --end 2026-05`: passed
- `pytest`: passed

## Separation Tests

The test suite locks these rules:

- System B `oil_market` report and code paths must not mix in CPI, rates, funding, carry, or yield curve concepts.
- System C `rates_cpi` report and package must not import or consume `oil_market` or `oil_rates_cpi`.
- System C report must not contain oil, WTI, Brent, inventory, refinery, or crack spread terms.
- System D `macro_integration` reads only A/B/C summary JSON files.
- System D must not read `oil_rates_cpi_summary.json`.
- Legacy `oil_rates_cpi` remains importable and test-covered.

## Mock And Real-Data Checks

- Missing FRED, EIA, or BLS keys must not crash a run.
- Mock fallback must be visible in warnings and chart/report labels as `MOCK DATA ONLY`.
- System B is real-data ready only when `fred_real_data=true`, `eia_real_data=true`, `real_data_ready=true`, and `data_validation_passed=true`.
- System C is real-data ready only when `fred_real_data=true`, `bls_real_data=true`, `real_data_ready=true`, and `data_validation_passed=true`.
- System D readiness is derived from A/B/C summary readiness fields only.
