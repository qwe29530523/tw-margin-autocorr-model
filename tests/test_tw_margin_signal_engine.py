import pandas as pd

from tw_margin_autocorr_model import ModelConfig, assign_signal_columns, write_summary


def test_assign_signal_columns_separates_raw_and_final_signal_with_reason_and_phase():
    df = pd.DataFrame(
        [
            {
                "date": "2026-06-04",
                "index_close": 45677.46,
                "index_yoy": 1.10,
                "index_qoq": 0.39,
                "margin_roc": 0.52,
                "margin_roc_autocorr": 0.96,
                "autocorr_high_threshold": 0.99,
                "index_yoy_z": 3.0,
                "index_qoq_z": 2.8,
                "margin_roc_z": 2.6,
                "margin_roc_autocorr_rank_252": 0.30,
                "margin_roc_persistence_score": 0.97,
            }
        ]
    )

    result = assign_signal_columns(df)
    latest = result.iloc[-1]

    assert latest["raw_signal"] == "NORMAL"
    assert latest["final_signal"] == "LATE_CYCLE_LEVERAGE_WARNING"
    assert "persistence" in latest["final_signal_reason"]
    assert latest["leverage_cycle_phase"] == "late_cycle_leverage_warning"
    assert latest["signal"] == latest["final_signal"]


def test_assign_signal_columns_adds_transition_watch_states():
    dates = pd.date_range("2026-01-01", periods=22)
    df = pd.DataFrame(
        {
            "date": dates,
            "index_close": [100.0] + [110.0] * 20 + [90.0],
            "index_yoy": 0.10,
            "index_qoq": [0.30] + [0.28] * 20 + [0.10],
            "margin_roc": [0.60] + [0.55] * 20 + [0.40],
            "margin_roc_autocorr": 0.50,
            "autocorr_high_threshold": 0.90,
            "index_yoy_z": 0.0,
            "index_qoq_z": 0.0,
            "margin_roc_z": 1.20,
            "margin_roc_autocorr_rank_252": 0.20,
            "margin_roc_persistence_score": 0.30,
        }
    )

    result = assign_signal_columns(df)
    latest = result.iloc[-1]

    assert "index_close_return_20d" in result.columns
    assert "margin_roc_change_20d" in result.columns
    assert latest["transition_watch"] == "deleveraging_risk_watch"

    distribution_row = result.iloc[20]
    assert distribution_row["transition_watch"] == "distribution_warning"


def test_write_summary_reports_raw_and_final_signal_fields(tmp_path):
    df = assign_signal_columns(
        pd.DataFrame(
            [
                {
                    "date": pd.Timestamp("2026-06-04"),
                    "index_close": 45677.46,
                    "margin_balance_thousand_ntd": 572635940.0,
                    "index_yoy": 1.10,
                    "index_qoq": 0.39,
                    "margin_roc": 0.52,
                    "margin_roc_autocorr": 0.96,
                    "autocorr_high_threshold": 0.99,
                    "index_yoy_z": 3.0,
                    "index_qoq_z": 2.8,
                    "margin_roc_z": 2.6,
                    "margin_roc_autocorr_percentile_full_sample": 0.06,
                    "margin_roc_autocorr_percentile": 0.06,
                    "margin_roc_autocorr_rank_252": 0.30,
                    "margin_roc_persistence_score": 0.97,
                }
            ]
        )
    )
    config = ModelConfig(
        start=pd.Timestamp("2012-01-01").date(),
        end=pd.Timestamp("2026-06-04").date(),
        index_yoy_window=252,
        index_qoq_window=63,
        margin_roc_window=63,
        autocorr_window=126,
        threshold_quantile=0.9,
        output_dir=tmp_path,
        force_refresh=False,
        max_workers=1,
        request_delay=0.0,
    )
    output_path = tmp_path / "signal_summary.json"

    write_summary(df, config, output_path, pd.DataFrame(), pd.DataFrame())

    summary = pd.read_json(output_path, typ="series")
    assert summary["data_quality_warning"] is False
    assert summary["market_extreme_warning"] is True
    assert summary["raw_signal"] == "NORMAL"
    assert summary["final_signal"] == "LATE_CYCLE_LEVERAGE_WARNING"
    assert "persistence" in summary["final_signal_reason"]
    assert summary["leverage_cycle_phase"] == "late_cycle_leverage_warning"
