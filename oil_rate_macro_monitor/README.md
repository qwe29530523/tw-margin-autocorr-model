# Oil Rate Macro Monitor

`oil_rate_macro_monitor` 是 **Global Oil / Inflation Pressure System**。它用來整理原油價格、WTI curve proxy、physical tightness、成品油壓力，以及油價如何傳導到 inflation / rates 的 macro pressure。

正式決策架構只能分成以下 5 層：

1. Oil Price & WTI Curve
2. Physical Tightness
3. Product Inventory Pressure
4. Oil → Inflation / Rates Transmission
5. Final Oil-Rate Macro Regime

fetchers、processors、validation、reports、charts、tests 都是 **Supporting Implementation Layers**。它們是支援資料讀取、轉換、檢查、呈現與驗證的工程層，不是額外的 macro decision systems，也不代表這個系統有 10 個核心子系統。

核心模式只使用 FRED + EIA，不把 Yahoo / yfinance 當核心資料源；Yahoo 只保留為 optional market overlay，預設關閉。

## 安裝

```bash
cd oil_rate_macro_monitor
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

macOS/Linux:

```bash
cd oil_rate_macro_monitor
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 建立 .env

複製範例檔：

```bash
copy .env.example .env
```

填入：

```text
FRED_API_KEY=
EIA_API_KEY=
USE_YAHOO=false
```

`FRED_API_KEY` 與 `EIA_API_KEY` 是核心資料源使用。`USE_YAHOO=false` 表示不抓 Yahoo overlay。`.env` 已列入 `.gitignore`，不要 commit。

## API key

FRED API key 可到 St. Louis Fed FRED 網站申請。申請後填入 `.env` 的 `FRED_API_KEY`。

EIA API key 可到 U.S. Energy Information Administration Open Data/API 頁面申請。申請後填入 `.env` 的 `EIA_API_KEY`。

## 執行方式

```bash
python -m src.main fetch
python -m src.main process
python -m src.main report
python -m src.main all
```

`fetch` 會抓 FRED 與 EIA 到 `data/raw/`，每個 raw 檔案都會帶 timestamp。若 `.env` 設定 `USE_YAHOO=true`，才會另外抓 Yahoo overlay。`process` 會輸出 `oil_engine` 與 `rates_curve` 到 `data/processed/`，優先使用 parquet，如果環境缺少 `pyarrow` 或 parquet engine，會 fallback 成 CSV。`report` 會產出 `data/reports/oil_rate_macro_report_YYYYMMDD.md`。

Dashboard：

```bash
streamlit run src/reports/dashboard.py
```

Dashboard、markdown report 與 chart modules 只屬於 Supporting Implementation Layers，用來呈現上述 5 層判斷結果，不新增正式決策層。

## 資料來源與限制

FRED 用來抓利率與油價序列，例如 `FEDFUNDS`、`SOFR`、`DGS3MO`、`DGS1`、`DGS2`、`DGS5`、`DGS10`、`DGS30`、`T10Y2Y`、`T10Y3M`、`DCOILWTICO`、`DCOILBRENTEU`。EIA 用來抓原油/汽油/餾分油庫存、煉廠開工率、煉廠原油投入、原油產量、原油出口、汽油/餾分油/航煤 product supplied，以及汽油、柴油、取暖油價格 proxy。

Yahoo Finance 不屬於核心資料源。若 `USE_YAHOO=true`，程式可以抓 optional market overlay，但報告會標註 Yahoo overlay 狀態。

免費資料源有延遲、欄位調整、API 限流與序列 ID 改版風險。EIA v2 的部分 series id 可能需要重新確認，如果某個 series 抓不到，程式會 logging 並跳過，不會讓整個流程中斷。

完整期貨曲線資料需要 CME/ICE/Nasdaq Data Link 或其他期貨期限結構資料源。核心 FRED+EIA 模式沒有 futures curve，`curve_state` 會標成 `unknown`，並在 warnings 裡註明。

Baker Hughes rig count 第一版先支援手動下載 CSV/XLSX，再用 `load_baker_hughes_rig_count(file_path)` 讀取與標準化。

## 正式決策輸出

Final Oil-Rate Macro Regime：

- `inflation_pressure`
- `growth_strength`
- `stagflation_risk`
- `recession_pressure`
- `supply_shock`
- `neutral_mixed`

輸出包含：

- `macro_regime`
- `secondary_regime`
- `confidence_score`
- `reasons`
- `warnings`

## 測試

```bash
python -m pytest tests
```

目前測試覆蓋：

- gasoline crack = `RB * 42 - WTI`
- diesel crack = `HO * 42 - WTI`
- Core FRED+EIA oil engine
- rates curve / carry / funding engine
- macro regime engine
- markdown report format
- inflation / recession / stagflation-or-supply-shock legacy regime 基本規則

以上測試項目屬於 Supporting Implementation Layers 的驗證範圍，不是額外的 macro decision systems。
