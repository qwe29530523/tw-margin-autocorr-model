# Macro Research System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a mock-safe macro research project split into TW margin cycle, oil/rates/CPI, and macro integration systems.

**Architecture:** Create a new `macro_research_system/` package beside legacy code. Each subsystem emits its own summary JSON and Markdown report. Fetchers read only environment variables and default to mock mode without crashing.

**Tech Stack:** Python 3.11+, pandas, numpy, matplotlib, pytest.

---

### Task 1: Scaffold and Safety Settings

**Files:**
- Create: `macro_research_system/.env.example`
- Create: `macro_research_system/.gitignore`
- Create: `macro_research_system/requirements.txt`
- Create: `macro_research_system/src/common/settings.py`

- [x] Create settings that read `FRED_API_KEY`, `EIA_API_KEY`, `BLS_API_KEY`, `USE_YAHOO`, and `MOCK_MODE`.
- [x] Default to mock mode when keys are missing.
- [x] Never print or write API keys.

### Task 2: System A TW Margin Cycle

**Files:**
- Create: `macro_research_system/src/systems/tw_margin_cycle/processors/signal_engine.py`
- Create: `macro_research_system/src/systems/tw_margin_cycle/processors/index_margin_engine.py`
- Create: `macro_research_system/src/systems/tw_margin_cycle/charts/index_margin_chart.py`
- Create: `macro_research_system/src/systems/tw_margin_cycle/reports/tw_margin_cycle_report.py`
- Create: `macro_research_system/src/systems/tw_margin_cycle/backtests/tw_margin_cycle_backtest.py`

- [x] Read legacy `output/` files when present.
- [x] Fall back to fixture data when legacy files are unavailable.
- [x] Emit `data/tw_margin_cycle/processed/tw_margin_cycle_summary.json`.
- [x] Emit chart and report.

### Task 3: System B Oil Rates CPI

**Files:**
- Create fetchers under `src/systems/oil_rates_cpi/fetchers/`.
- Create processors under `src/systems/oil_rates_cpi/processors/`.
- Create reports and backtest skeletons.

- [x] Fetchers use mock data unless API keys exist and mock mode is false.
- [x] Rates spreads use same-date DGS curve as primary signal.
- [x] CPI nowcast does not use actual CPI values.
- [x] Emit `oil_rates_cpi_summary.json` and report.

### Task 4: System C Integration

**Files:**
- Create: `macro_research_system/src/systems/macro_integration/signal_adapter.py`
- Create: `macro_research_system/src/systems/macro_integration/regime_matrix.py`
- Create: `macro_research_system/src/systems/macro_integration/allocation_rules.py`
- Create: `macro_research_system/src/systems/macro_integration/integrated_report.py`

- [x] Read only summary JSONs.
- [x] Emit integrated summary JSON and report.

### Task 5: CLI and Tests

**Files:**
- Create: `macro_research_system/src/main.py`
- Create tests under `macro_research_system/tests/`.

- [x] Support `run-tw-margin`, `run-oil-rates-cpi`, `run-integrated`, `run-all`.
- [x] Support backtest subcommands.
- [x] Verify pytest passes with mock data.
