from src.systems.tw_margin_cycle.processors.signal_engine import classify_tw_margin_cycle
import pandas as pd

from src.systems.tw_margin_cycle.charts.index_margin_chart import (
    CHART_PANEL_COUNT,
    MAIN_CYCLE_CHART_NAME,
    ORIGINAL_STYLE_CHART_NAME,
    ORIGINAL_STYLE_RECENT5Y_CHART_NAME,
    ORIGINAL_STYLE_TITLE,
    PERCENT_CYCLE_CHART_NAME,
    PERCENT_CYCLE_TITLE,
    RECENT5Y_CYCLE_CHART_NAME,
    RECENT5Y_PERCENT_CYCLE_CHART_NAME,
    STANDARDIZED_CYCLE_TITLE,
    filter_recent_years,
    prepare_original_style_frame,
    prepare_percent_cycle_frame,
    prepare_standardized_cycle_frame,
    signal_transition_points,
    write_original_style_chart,
    write_percent_cycle_chart,
    write_standardized_cycle_chart,
)
from src.systems.tw_margin_cycle.processors.index_margin_engine import build_tw_margin_cycle_summary, run_tw_margin_cycle
from src.systems.tw_margin_cycle.reports.tw_margin_cycle_report import write_tw_margin_cycle_report


def test_tw_raw_signal_and_final_signal_are_not_confused():
    row = {
        "raw_signal": "NORMAL",
        "index_yoy_z": 3.0,
        "index_qoq_z": 2.5,
        "margin_roc_z": 2.4,
        "margin_roc": 0.52,
        "margin_roc_persistence_score": 0.95,
    }

    result = classify_tw_margin_cycle(row)

    assert result["raw_signal"] == "NORMAL"
    assert result["final_signal"] == "LATE_CYCLE_LEVERAGE_WARNING"
    assert result["leverage_cycle_phase"] == "late_cycle_leverage_warning"


def test_tw_late_cycle_leverage_warning_rule():
    row = {
        "index_yoy_z": 2.8,
        "index_qoq_z": 2.2,
        "margin_roc_z": 2.5,
        "margin_roc": 0.50,
        "margin_roc_persistence_score": 0.90,
        "index_close_return_20d": 0.04,
        "margin_roc_change_20d": 0.10,
    }

    result = classify_tw_margin_cycle(row)

    assert result["final_signal"] == "LATE_CYCLE_LEVERAGE_WARNING"
    assert result["risk_level"] == "high"


def test_tw_deleveraging_risk_rule():
    row = {
        "index_yoy_z": 1.0,
        "index_qoq_z": -1.5,
        "margin_roc_z": -0.5,
        "margin_roc": 0.10,
        "margin_roc_persistence_score": 0.20,
        "index_close_return_20d": -0.08,
        "index_close_return_60d": -0.12,
        "margin_roc_change_20d": -0.20,
        "margin_balance_change_20d": -10000,
        "market_extreme_warning": True,
    }

    result = classify_tw_margin_cycle(row)

    assert result["final_signal"] == "DELEVERAGING_RISK"
    assert result["leverage_cycle_phase"] == "deleveraging_risk"


def test_tw_index_margin_chart_declares_three_panel_layout():
    assert CHART_PANEL_COUNT == 3


def test_tw_standardized_cycle_chart_has_dedicated_name_and_title(tmp_path):
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=3),
            "index_yoy_z": [0.5, 2.1, 1.2],
            "margin_roc_z": [0.3, 2.4, 1.0],
            "margin_balance_thousand_ntd": [100, 150, 140],
            "final_signal": ["NORMAL", "LATE_CYCLE_LEVERAGE_WARNING", "DELEVERAGING_RISK"],
        }
    )
    output = tmp_path / MAIN_CYCLE_CHART_NAME

    path = write_standardized_cycle_chart(frame, output)

    assert path.name == "margin_index_yoy_standardized_cycle.png"
    assert STANDARDIZED_CYCLE_TITLE == "TW Margin × Index YoY Standardized Cycle"
    assert path.exists()
    assert path.stat().st_size > 0


def test_tw_percent_cycle_frame_uses_percentage_columns():
    periods = 253
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2025-01-01", periods=periods, freq="B"),
            "index_yoy": [0.10] * (periods - 1) + [0.55],
            "index_qoq": [0.02] * (periods - 1) + [0.18],
            "margin_roc": [0.05] * (periods - 1) + [0.42],
            "margin_balance_thousand_ntd": [100.0] + [120.0] * (periods - 2) + [150.0],
            "final_signal": ["NORMAL"] * periods,
        }
    )

    result = prepare_percent_cycle_frame(frame)

    assert round(result["index_yoy_pct"].iloc[-1], 6) == 55.0
    assert round(result["index_qoq_pct"].iloc[-1], 6) == 18.0
    assert round(result["margin_roc_pct"].iloc[-1], 6) == 42.0
    assert round(result["margin_balance_yoy_pct"].iloc[-1], 6) == 50.0


def test_tw_original_style_frame_uses_index_yoy_qoq_and_margin_yoy_lines():
    periods = 253
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2025-01-01", periods=periods, freq="B"),
            "index_yoy": [0.10] * (periods - 1) + [0.55],
            "index_qoq": [0.02] * (periods - 1) + [0.18],
            "margin_roc": [0.03] * periods,
            "margin_balance_thousand_ntd": [100.0] + [120.0] * (periods - 2) + [150.0],
            "final_signal": ["NORMAL"] * periods,
        }
    )

    result = prepare_original_style_frame(frame)

    assert "index_yoy_pct_plot" in result.columns
    assert "index_qoq_pct_plot" in result.columns
    assert "margin_balance_yoy_pct_plot" in result.columns
    assert "margin_roc_pct_plot" not in result.columns
    assert round(result["index_yoy_pct_plot"].iloc[-1], 6) == 19.0
    assert round(result["index_qoq_pct_plot"].iloc[-1], 6) == 5.2
    assert round(result["margin_balance_yoy_pct_plot"].iloc[-1], 6) == 50.0


def test_tw_percent_cycle_chart_can_write_full_and_recent_5y(tmp_path):
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2018-01-01", periods=600, freq="B"),
            "index_yoy": [0.15] * 600,
            "index_qoq": [0.08] * 600,
            "margin_roc": [0.12] * 600,
            "margin_balance_thousand_ntd": [100.0 + index for index in range(600)],
            "final_signal": ["NORMAL"] * 599 + ["LATE_CYCLE_LEVERAGE_WARNING"],
        }
    )

    full_path = write_percent_cycle_chart(frame, tmp_path / PERCENT_CYCLE_CHART_NAME)
    recent_path = write_percent_cycle_chart(
        frame,
        tmp_path / RECENT5Y_PERCENT_CYCLE_CHART_NAME,
        recent_years=5,
    )

    assert full_path.name == "margin_index_yoy_percent_cycle.png"
    assert recent_path.name == "margin_index_yoy_percent_cycle_recent5y.png"
    assert PERCENT_CYCLE_TITLE == "TW Margin × Index YoY Percent Cycle"
    assert full_path.exists()
    assert full_path.stat().st_size > 0
    assert recent_path.exists()
    assert recent_path.stat().st_size > 0


def test_tw_original_style_chart_can_write_clean_observation_charts(tmp_path):
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2018-01-01", periods=600, freq="B"),
            "index_yoy": [0.15] * 600,
            "index_qoq": [0.08] * 600,
            "margin_roc": [0.12] * 600,
            "margin_balance_thousand_ntd": [100.0 + index for index in range(600)],
            "final_signal": ["NORMAL"] * 599 + ["LATE_CYCLE_LEVERAGE_WARNING"],
        }
    )

    full_path = write_original_style_chart(frame, tmp_path / ORIGINAL_STYLE_CHART_NAME)
    recent_path = write_original_style_chart(
        frame,
        tmp_path / ORIGINAL_STYLE_RECENT5Y_CHART_NAME,
        recent_years=5,
    )

    assert full_path.name == "margin_index_original_style.png"
    assert recent_path.name == "margin_index_original_style_recent5y.png"
    assert ORIGINAL_STYLE_TITLE == "TW Margin × Index YoY Cycle"
    assert full_path.exists()
    assert full_path.stat().st_size > 0
    assert recent_path.exists()
    assert recent_path.stat().st_size > 0


def test_tw_standardized_cycle_chart_can_write_recent_5y_zoom(tmp_path):
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2018-01-01", "2026-06-01", freq="180D"),
            "index_yoy_z": [0.1, 0.3, 0.5, 0.7, 0.8, 1.0, 1.2, 1.5, 1.1, 0.8, 0.3, -0.2, 0.6, 1.4, 2.0, 2.4, 1.8, 1.2],
            "margin_roc_z": [0.0, 0.2, 0.4, 0.3, 0.5, 0.8, 1.0, 1.3, 1.7, 1.5, 1.2, 0.6, 0.2, 1.0, 1.8, 2.3, 1.7, 0.9],
            "margin_balance_percentile": [20, 25, 30, 35, 40, 45, 50, 55, 58, 60, 65, 70, 75, 80, 85, 90, 88, 84],
            "final_signal": ["NORMAL"] * 14 + ["LATE_CYCLE_LEVERAGE_WARNING"] * 2 + ["NORMAL", "DELEVERAGING_RISK"],
        }
    )
    output = tmp_path / RECENT5Y_CYCLE_CHART_NAME

    path = write_standardized_cycle_chart(frame, output, recent_years=5)

    assert path.name == "margin_index_yoy_standardized_cycle_recent5y.png"
    assert path.exists()
    assert path.stat().st_size > 0


def test_filter_recent_years_keeps_only_latest_window():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(
                [
                    "2018-01-01",
                    "2019-01-01",
                    "2020-01-01",
                    "2021-01-01",
                    "2021-06-01",
                    "2022-01-01",
                    "2023-01-01",
                    "2024-01-01",
                    "2025-01-01",
                    "2026-06-01",
                ]
            ),
            "index_yoy_z": range(10),
        }
    )

    result = filter_recent_years(frame, years=5)

    assert result["date"].min() >= pd.Timestamp("2021-06-01")
    assert result["date"].max() == pd.Timestamp("2026-06-01")


def test_tw_standardized_cycle_chart_normalizes_margin_percentile_to_single_axis():
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=3),
            "index_yoy_z": [0.0, 2.0, 5.0],
            "margin_roc_z": [0.0, 2.0, 5.0],
            "margin_balance_percentile": [0.0, 50.0, 100.0],
            "final_signal": ["NORMAL", "NORMAL", "NORMAL"],
        }
    )

    result = prepare_standardized_cycle_frame(frame)

    assert result["margin_balance_percentile_z"].tolist() == [-3.0, 0.0, 3.0]
    assert "index_yoy_z_plot" in result.columns
    assert "margin_roc_z_plot" in result.columns
    assert "margin_balance_percentile_z_plot" in result.columns


def test_tw_standardized_cycle_chart_marks_signal_transition_days_only():
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=6),
            "index_yoy_z": [0, 1, 2, 2, 1, -1],
            "margin_roc_z": [0, 1, 2, 2, 1, -2],
            "margin_balance_percentile": [10, 20, 90, 95, 80, 40],
            "final_signal": [
                "NORMAL",
                "LATE_CYCLE_LEVERAGE_WARNING",
                "LATE_CYCLE_LEVERAGE_WARNING",
                "NORMAL",
                "DELEVERAGING_RISK",
                "DELEVERAGING_RISK",
            ],
        }
    )

    transitions = signal_transition_points(prepare_standardized_cycle_frame(frame))

    assert transitions["date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-01-02", "2026-01-05"]
    assert transitions["final_signal"].tolist() == ["LATE_CYCLE_LEVERAGE_WARNING", "DELEVERAGING_RISK"]


def test_tw_margin_cycle_summary_adds_margin_balance_percentile(tmp_path):
    input_dir = tmp_path / "legacy_output"
    input_dir.mkdir()
    pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=3),
            "index_close": [100, 110, 120],
            "index_yoy": [0.1, 0.2, 0.3],
            "index_qoq": [0.05, 0.06, 0.07],
            "margin_balance_thousand_ntd": [100, 150, 200],
            "margin_roc": [0.1, 0.3, 0.5],
            "index_yoy_z": [1.0, 2.0, 3.0],
            "index_qoq_z": [0.5, 0.6, 0.7],
            "margin_roc_z": [0.8, 1.8, 2.8],
            "margin_roc_autocorr": [0.4, 0.5, 0.6],
            "margin_roc_persistence_score": [0.4, 0.6, 0.9],
            "raw_signal": ["NORMAL", "NORMAL", "NORMAL"],
        }
    ).to_csv(input_dir / "tw_margin_autocorr_model.csv", index=False)
    (input_dir / "signal_summary.json").write_text('{"market_extreme_warning": true}', encoding="utf-8")

    summary, frame = build_tw_margin_cycle_summary(input_dir)

    assert "margin_balance_percentile" in frame.columns
    assert summary["margin_balance_percentile"] == 100.0


def test_tw_margin_cycle_report_prefers_percent_main_chart(tmp_path):
    summary = {
        "report_date": "2026-06-09",
        "raw_signal": "NORMAL",
        "final_signal": "LATE_CYCLE_LEVERAGE_WARNING",
        "leverage_cycle_phase": "late_cycle_leverage_warning",
        "risk_level": "high",
        "market_extreme_warning": True,
        "data_quality_warning": False,
        "data_end": "2026-06-09",
        "index_close": 23000.0,
        "index_yoy": 0.5,
        "index_qoq": 0.1,
        "margin_balance_thousand_ntd": 200000000.0,
        "margin_balance_percentile": 98.0,
        "margin_roc": 0.6,
        "margin_roc_autocorr": 0.7,
        "margin_roc_persistence_score": 0.9,
        "final_signal_reasons": ["test"],
        "warnings": [],
    }

    report_path = write_tw_margin_cycle_report(summary, tmp_path)
    report = report_path.read_text(encoding="utf-8")

    assert "Main chart: data/tw_margin_cycle/charts/margin_index_original_style.png" in report
    assert "Recent 5Y chart: data/tw_margin_cycle/charts/margin_index_original_style_recent5y.png" in report
    assert "secondary percent chart path: margin_index_yoy_percent_cycle.png" in report
    assert "secondary z-score chart path: margin_index_yoy_standardized_cycle.png" in report
    assert "detailed chart path: index_margin_cycle.png" in report
    assert "本圖為原始觀察圖，使用同一個百分比尺度比較融資年增率、台股指數季增率與台股指數年增率" in report
