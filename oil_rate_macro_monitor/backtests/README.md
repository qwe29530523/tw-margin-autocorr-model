# Oil Signal Backtest Layer

這個資料夾是 `oil_rate_macro_monitor` 的 **Supporting Research Layer**。

它不是 production macro decision layer，不會修改現有 production scoring，也不會改變 Final Oil-Rate Macro Regime 的核心判斷邏輯。

## 目的

`oil_signal_backtest.py` 用來評估 Energy / Oil Inflation Pressure Subsystem 裡的候選 signal 是否有足夠 evidence 進入未來 production score。

目前評估的 signal 類型包含：

- oil price momentum / oil price regime
- WTI curve state
- physical tightness
- product inventory pressure
- inflation / rates transmission
- source confidence / missing data flags

WTI curve state 若缺資料，會明確標記 missing，不會 forward fill，不會硬補，也不會假造 futures curve。正式 WTI curve source 必須提供同一天的 `cl_m1_settle`、`cl_m2_settle`、`cl_m3_settle`，並標記 `source_type=production_api` 或 `production_vendor`。Yahoo `CL=F` / continuous front-month 不可作為 M1/M2/M3 curve source。

## Forward Horizons

目前預設回測：

- 4 weeks
- 8 weeks
- 13 weeks

## Targets

若資料欄位存在，回測會評估：

- WTI forward return
- 10Y yield forward change
- breakeven inflation forward change
- risk asset proxy forward return / drawdown

缺少的 target 會被跳過，不會讓流程 crash。

Risk asset proxy 第一版優先使用 SPY。若 backtest 從 `data/raw/yahoo_*.csv` 讀到 SPY，summary 會標記 `target_source=Yahoo SPY` 與 `target_source_type=research_only`。Yahoo overlay 只作為 research-only target source，不是 production-grade market data source，也不應被直接用於 production scoring。

## Output

預設輸出：

```text
oil_rate_macro_monitor/exports/oil_signal_backtest_summary.json
```

`exports/` 屬於 local research output，不應被 force add 進 Git。

## Input Discovery

Backtest 會先嘗試讀取 legacy weekly CSV：

```text
oil_rate_macro_monitor/output/oil_rate_inflation_weekly_data.csv
```

目前 `oil_rate_macro_monitor` 的正式 pipeline 實際輸出在：

```text
oil_rate_macro_monitor/data/processed/oil_engine.csv
oil_rate_macro_monitor/data/processed/rates_curve.csv
```

若 legacy weekly CSV 不存在，backtest 會只在 research layer 內讀取上述 processed outputs，合併後 resample 成 `W-FRI` 週頻資料。這不會搬資料夾、不會產生 production scoring，也不會修改 production pipeline。

每筆 summary 至少包含：

- signal_name
- target_name
- horizon_weeks
- sample_count
- hit_rate
- average_forward_return
- median_forward_return
- average_forward_drawdown
- information_coefficient
- missing_data_ratio
- suggested_direction
- suggested_weight_range
- usable_for_score

## 執行方式

```bash
python oil_rate_macro_monitor/backtests/oil_signal_backtest.py
```

也可以指定 input / output：

```bash
python oil_rate_macro_monitor/backtests/oil_signal_backtest.py ^
  --input-path oil_rate_macro_monitor/output/oil_rate_inflation_weekly_data.csv ^
  --output-path oil_rate_macro_monitor/exports/oil_signal_backtest_summary.json ^
  --horizons-weeks 4 8 13
```

## Production Rule

本階段只做：

- signal validation
- suggested score direction
- suggested score weight range

正式 production score 必須等 backtest evidence 確認後才建立。這個 layer 的 `suggested_weight_range` 只是研究輸出，不是正式權重，也不應直接寫死進 production scoring。
