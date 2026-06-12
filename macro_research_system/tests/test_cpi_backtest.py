from src.systems.oil_rates_cpi.backtests.cpi_nowcast_backtest import run_cpi_nowcast_backtest


def test_cpi_backtest_mock_metrics():
    result = run_cpi_nowcast_backtest(mock_mode=True)

    assert result["system"] == "cpi_nowcast_backtest"
    assert result["status"] == "mock_only"
    assert result["mae"] is None
    assert result["rmse"] is None
    assert result["warnings"]
