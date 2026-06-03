# TW Margin Autocorr Model

這個專案用來追蹤台股加權指數與台股集中市場融資餘額變化率之間的狀態。第一版採用 TWSE 官方 JSON 資料，建立每日 dataframe，計算指數成長、融資變化率與融資變化率的 rolling autocorrelation，並輸出 CSV、圖表與最新 signal 摘要。

## 模型用途

模型不是交易建議，而是一個市場槓桿溫度計。它觀察加權指數動能與融資餘額變化是否同向、是否有持續性，協助辨識市場槓桿升溫、行情轉弱但槓桿仍堆高，或融資去化壓力升高的區段。

## 圖表線條

`output/tw_margin_autocorr_growth.png` 會顯示三條主要線：

- 黃線：`index_yoy`，加權指數年增率，預設用 252 個交易日計算。
- 藍線：`index_qoq`，加權指數季增率，預設用 63 個交易日計算。
- 灰線：`margin_roc`，集中市場融資金額餘額變化率，預設用 63 個交易日計算。

## 自相關高分位數的意義

`margin_roc_autocorr` 是融資變化率在 rolling window 內的一階自相關，預設 window 為 126 個交易日。當它高於 `autocorr_high_threshold`，代表融資變化率近期有較強持續性。預設 threshold 是樣本分位數 0.90，也就是只把歷史上自相關最高的前 10% 區間標成高持續性狀態。

高自相關本身不代表多空方向，還要搭配 `margin_roc` 與指數動能判斷：

- `HOT_LEVERAGE_MOMENTUM`：融資增加、指數季動能為正，且融資變化持續性偏高。
- `LATE_CYCLE_LEVERAGE_WARNING`：指數年動能仍為正，但季動能轉弱，融資仍增加且持續性偏高。
- `DELEVERAGING_RISK`：融資下降、指數季動能為負，且融資變化持續性偏高。
- `NORMAL`：未落入上述狀態。

## 本機執行

```bash
python -m pip install -r requirements.txt
python tw_margin_autocorr_model.py --start 2012-01-01
```

輸出會寫到 `output/`：

- `output/tw_margin_autocorr_model.csv`
- `output/tw_margin_autocorr_growth.png`
- `output/tw_margin_autocorr_signal.png`
- `output/signal_summary.json`

第一次從 2012 年開始抓融資日資料會比較久。之後如果 `output/tw_margin_autocorr_model.csv` 已存在，腳本會沿用其中的融資餘額資料，只補尚未存在的交易日。

## CLI 參數

常用參數如下：

```bash
python tw_margin_autocorr_model.py \
  --start 2012-01-01 \
  --end 2026-06-03 \
  --index-yoy-window 252 \
  --index-qoq-window 63 \
  --margin-roc-window 63 \
  --autocorr-window 126 \
  --threshold-quantile 0.90
```

其他實用參數：

- `--output-dir output`：調整輸出目錄。
- `--force-refresh`：忽略既有 CSV 快取，重新抓取所有融資資料。
- `--max-workers 4`：調整資料並行抓取數。
- `--request-delay 0.0`：每次融資 API 請求前等待秒數。

## 手動執行 GitHub Actions

到 GitHub repo 頁面後：

1. 打開 `Actions`。
2. 選擇 `Run TW Margin Autocorr Model` workflow。
3. 點選 `Run workflow`。
4. 選擇 branch 後再次按下 `Run workflow`。

Workflow 也會在週一到週五台灣時間 18:30 自動執行，更新 `output/` 裡的 CSV、PNG、JSON，並 commit 回 repo。

## 資料來源

- 加權指數歷史資料：TWSE `MI_5MINS_HIST`
- 集中市場融資融券餘額：TWSE `MI_MARGN`
