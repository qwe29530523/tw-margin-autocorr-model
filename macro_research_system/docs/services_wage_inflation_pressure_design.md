# Services / Wage Inflation Pressure Subsystem V1

The Services / Wage Inflation Pressure Subsystem is a component of the Inflation Pressure Composite. It is not a full inflation score and does not produce a production score in V1.

Preferred V1 sources are FRED and BLS. BEA can be added later as an official extension if compensation or income data becomes useful. Yahoo and other unofficial sources are not allowed as production sources.

The existing BLS core services ex shelter proxy is `CUUR0000SASLE`. Medical services, transportation services, and recreation services CPI component IDs must be verified against official BLS or FRED metadata before implementation.

Missing data must not crash the pipeline. Missing values should be carried into diagnostics through missing-data ratios and source-confidence fields rather than replaced with synthetic observations.

Services and wage inflation have sticky and lagged transmission. The 3m, 6m, and 12m horizons should be emphasized more than 1m for validation and backtesting.

## Processor Output Contract

The V1 processor produces a monthly Services / Wage research frame. The expected raw inputs are:

- `core_services_ex_shelter_proxy`
- `average_hourly_earnings`
- `employment_cost_index_wages`
- `unit_labor_cost`
- `compensation_per_hour`
- `nonfarm_payrolls`
- `unemployment_rate`
- `job_openings`
- `quits_rate`
- `initial_claims`
- `continuing_claims`

The V1 processor output contract includes transparent change fields, candidate pressure signals, and source diagnostics:

- `core_services_1m_chg`
- `core_services_3m_chg`
- `wage_ahe_3m_roc`
- `eci_3m_roc`
- `unit_labor_cost_3m_roc`
- `compensation_per_hour_3m_roc`
- `payrolls_3m_roc`
- `unemployment_rate_3m_chg`
- `job_openings_3m_roc`
- `quits_rate_3m_chg`
- `initial_claims_3m_chg`
- `continuing_claims_3m_chg`
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
- `missing_data_ratio`
- `source_confidence`
- `source_mode`

## Backtest Summary Contract

The V1 backtest follows the Food / Shelter summary schema. Candidate signals are evaluated against forward services CPI, core CPI, headline CPI, breakeven inflation, rates, and risk-asset drawdown targets when those target columns are available.

Each backtest summary row includes:

- `signal_name`
- `target_name`
- `horizon_months`
- `sample_count`
- `hit_rate`
- `information_coefficient`
- `missing_data_ratio`
- `target_missing_data_ratio`
- `suggested_direction`
- `suggested_weight_range`
- `usable_for_score`
- `unusable_reason`
- `source_columns`
- `feature_role`

`source_confidence` is diagnostic-only. It must not receive a directional suggested weight range.

`usable_for_score` is an evidence-only gate, not production weighting. A signal can only be marked usable for future score design after sufficient sample count, target availability, missing-data checks, and backtest evidence. This subsystem does not create production weights in V1.

WTI curve API validation remains pending under Energy / Oil and is not closed by Services / Wage work. Yahoo and `CL=F` must not be used as WTI M1/M2/M3 curve sources.
