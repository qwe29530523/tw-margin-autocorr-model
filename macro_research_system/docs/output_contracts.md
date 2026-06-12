# Output Contracts

This document locks the current A/B/C/D macro research system contracts.

## System A: `tw_margin_cycle`

- Monitor: TW Margin × Index Growth
- CLI: `python -m src.main run-tw-margin`
- Backtest CLI: `python -m src.main backtest-tw-margin --start 2012-01-01 --end 2026-06-04`
- Summary: `data/tw_margin_cycle/processed/tw_margin_cycle_summary.json`
- Report: `data/tw_margin_cycle/reports/tw_margin_cycle_report_YYYYMMDD.md`
- Charts: `data/tw_margin_cycle/charts/`
- Backtest: `data/tw_margin_cycle/backtests/tw_margin_cycle_backtest.json`
- Mock fallback: allowed when legacy TW input files are missing.
- Ready marker: `mock_mode=false`.
- Important fields:
  - `system`
  - `mock_mode`
  - `report_date`
  - `final_signal`
  - `leverage_cycle_phase`
  - `risk_level`
  - `index_yoy`
  - `index_qoq`
  - `margin_roc`
  - `warnings`

## System B: `oil_market`

- Monitor: Crude Oil Market Monitor
- CLI: `python -m src.main run-oil-market`
- Backtest CLI: `python -m src.main backtest-oil-market --start 2018-01-01 --end 2026-06-08`
- Summary: `data/oil_market/processed/oil_market_summary.json`
- Report: `data/oil_market/reports/oil_market_report_YYYYMMDD.md`
- Charts:
  - `data/oil_market/charts/oil_price_momentum.png`
  - `data/oil_market/charts/oil_inventory_proxy.png`
  - `data/oil_market/charts/oil_product_demand.png`
  - `data/oil_market/charts/oil_crack_spread.png`
  - `data/oil_market/charts/oil_market_dashboard.png`
- Backtest: `data/oil_market/backtests/oil_regime_backtest.json`
- Mock fallback: allowed when `MOCK_MODE=true`, `FRED_API_KEY` is missing, `EIA_API_KEY` is missing, or a request fails.
- Ready markers:
  - `mock_mode=false`
  - `fred_real_data=true`
  - `eia_real_data=true`
  - `real_data_ready=true`
  - `data_validation_passed=true`
- Important fields:
  - `system="oil_market"`
  - `data_source_mode="Core FRED + EIA"`
  - `oil_regime`
  - `oil_momentum_signal`
  - `inventory_signal`
  - `product_demand_signal`
  - `supply_signal`
  - `price_war_risk`
  - `supply_shock_risk`
  - `demand_destruction_risk`
  - `data_completeness_score`
  - `regime_confidence_score`
  - `warnings`
- Separation rule: must not include rates, CPI, funding, carry, or yield curve inputs.

## System C: `rates_cpi`

- Monitor: Rates × CPI Monitor
- CLI: `python -m src.main run-rates-cpi`
- Backtest CLI: `python -m src.main backtest-cpi --start 2018-01 --end 2026-05`
- Summary: `data/rates_cpi/processed/rates_cpi_summary.json`
- Report: `data/rates_cpi/reports/rates_cpi_report_YYYYMMDD.md`
- Charts:
  - `data/rates_cpi/charts/rates_curve.png`
  - `data/rates_cpi/charts/cpi_nowcast.png`
  - `data/rates_cpi/charts/cpi_component_trends.png`
  - `data/rates_cpi/charts/rates_cpi_dashboard.png`
- Backtest: `data/rates_cpi/backtests/cpi_nowcast_backtest.json`
- Mock fallback: allowed when `MOCK_MODE=true`, `FRED_API_KEY` is missing, `BLS_API_KEY` is missing, or a request fails.
- Ready markers:
  - `mock_mode=false`
  - `fred_real_data=true`
  - `bls_real_data=true`
  - `real_data_ready=true`
  - `data_validation_passed=true`
- Important fields:
  - `system="rates_cpi"`
  - `data_source_mode="Core FRED + BLS"`
  - `rates_asof_date`
  - `cpi_asof_month`
  - `rates_regime`
  - `funding_pressure_signal`
  - `carry_signal`
  - `curve_signal`
  - `cpi_nowcast_signal`
  - `fed_funds`
  - `sofr`
  - `rate_3m`
  - `rate_1y`
  - `rate_2y`
  - `rate_5y`
  - `rate_10y`
  - `rate_30y`
  - `spread_10y_3m`
  - `spread_10y_2y`
  - `spread_5y_2y`
  - `spread_30y_10y`
  - `sofr_fed_funds_spread`
  - `three_month_fed_funds_spread`
  - `headline_cpi_mom_nowcast`
  - `headline_cpi_yoy_nowcast`
  - `core_cpi_mom_nowcast`
  - `core_cpi_yoy_nowcast`
  - `data_completeness_score`
  - `regime_confidence_score`
  - `warnings`
- Separation rule: must not include oil, WTI, Brent, inventory, refinery, or crack spread inputs.
- Backtest note: CPI nowcast backtest is contract-ready, but metrics remain scaffold/mock-only until point-in-time CPI vintages are wired.

## System D: `macro_integration`

- Monitor: Integrated Macro Monitor
- CLI: `python -m src.main run-integrated`
- Summary: `data/integrated/processed/integrated_macro_summary.json`
- Report: `data/integrated/reports/integrated_macro_report_YYYYMMDD.md`
- Charts:
  - `data/integrated/charts/integrated_risk_scores.png`
- Backtest: no formal System D backtest is sealed yet.
- Mock fallback: no raw-data fallback. The integration layer warns and lowers readiness when an input summary is missing, mock, or not validation-ready.
- Ready markers:
  - `tw_margin_system_ready=true`
  - `oil_market_system_ready=true`
  - `rates_cpi_system_ready=true`
- Important fields:
  - `system="macro_integration"`
  - `report_date`
  - `tw_margin_system_ready`
  - `oil_market_system_ready`
  - `rates_cpi_system_ready`
  - `tw_margin_final_signal`
  - `tw_leverage_cycle_phase`
  - `tw_risk_level`
  - `oil_regime`
  - `oil_momentum_signal`
  - `inventory_signal`
  - `product_demand_signal`
  - `supply_signal`
  - `price_war_risk`
  - `supply_shock_risk`
  - `demand_destruction_risk`
  - `rates_regime`
  - `funding_pressure_signal`
  - `carry_signal`
  - `curve_signal`
  - `cpi_nowcast_signal`
  - `equity_risk_score`
  - `bond_support_score`
  - `inflation_risk_score`
  - `deleveraging_risk_score`
  - `commodity_pressure_score`
  - `macro_tightening_score`
  - `final_market_state`
  - `asset_allocation_view`
  - `integration_reasons`
  - `warnings`
- Separation rule: reads only A/B/C summary JSON files and must not read `data/oil_rates_cpi/processed/oil_rates_cpi_summary.json`.

## Legacy: `oil_rates_cpi`

- CLI: `python -m src.main run-oil-rates-cpi`
- Summary: `data/oil_rates_cpi/processed/oil_rates_cpi_summary.json`
- Report: `data/oil_rates_cpi/reports/oil_rates_cpi_report_YYYYMMDD.md`
- Backtests:
  - `data/oil_rates_cpi/backtests/cpi_nowcast_backtest.json`
  - `data/integrated/backtests/` may contain older legacy macro-regime backtest output.
- Status: legacy mixed macro system.
- Integration rule: not a formal input to System D.

## Global CLI

```bash
python -m src.main run-all
```

`run-all` order:

```text
run-tw-margin
run-oil-market
run-rates-cpi
run-integrated
```
