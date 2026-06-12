from __future__ import annotations

import argparse
from pathlib import Path

from src.common.io import ensure_dir
from src.systems.macro_integration.integrated_report import run_integrated
from src.systems.oil_market.backtests.oil_regime_backtest import run_oil_regime_backtest
from src.systems.oil_market.processors.oil_market_runner import run_oil_market
from src.systems.oil_rates_cpi.backtests.macro_regime_backtest import run_macro_regime_backtest
from src.systems.oil_rates_cpi.processors.macro_regime_engine import run_oil_rates_cpi
from src.systems.rates_cpi.backtests.cpi_nowcast_backtest import (
    run_cpi_nowcast_backtest as run_rates_cpi_nowcast_backtest,
)
from src.systems.rates_cpi.processors.rates_cpi_runner import run_rates_cpi
from src.systems.tw_margin_cycle.backtests.tw_margin_cycle_backtest import run_tw_margin_cycle_backtest
from src.systems.tw_margin_cycle.processors.index_margin_engine import run_tw_margin_cycle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Macro research system CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["run-tw-margin", "run-oil-market", "run-oil-rates-cpi", "run-rates-cpi", "run-integrated", "run-all"]:
        sub.add_parser(name)
    tw = sub.add_parser("backtest-tw-margin")
    tw.add_argument("--start", default="2012-01-01")
    tw.add_argument("--end", default="2026-06-04")
    cpi = sub.add_parser("backtest-cpi")
    cpi.add_argument("--start", default="2018-01")
    cpi.add_argument("--end", default="2026-05")
    integ = sub.add_parser("backtest-integrated")
    integ.add_argument("--start", default="2018-01-01")
    integ.add_argument("--end", default="2026-06-08")
    oil = sub.add_parser("backtest-oil-market")
    oil.add_argument("--start", default="2018-01-01")
    oil.add_argument("--end", default="2026-06-08")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    data_root = ensure_dir(Path("data"))
    if args.command == "run-tw-margin":
        run_tw_margin_cycle(data_root)
    elif args.command == "run-oil-market":
        run_oil_market(data_root)
    elif args.command == "run-oil-rates-cpi":
        run_oil_rates_cpi(data_root)
    elif args.command == "run-rates-cpi":
        run_rates_cpi(data_root)
    elif args.command == "run-integrated":
        run_integrated(data_root)
    elif args.command == "run-all":
        run_tw_margin_cycle(data_root)
        run_oil_market(data_root)
        run_rates_cpi(data_root)
        run_integrated(data_root)
    elif args.command == "backtest-tw-margin":
        run_tw_margin_cycle_backtest(args.start, args.end, data_root / "tw_margin_cycle" / "backtests")
    elif args.command == "backtest-cpi":
        run_rates_cpi_nowcast_backtest(args.start, args.end, data_root / "rates_cpi" / "backtests")
    elif args.command == "backtest-integrated":
        run_macro_regime_backtest(args.start, args.end, data_root / "integrated" / "backtests")
    elif args.command == "backtest-oil-market":
        run_oil_regime_backtest(args.start, args.end, data_root / "oil_market" / "backtests")


if __name__ == "__main__":
    main()
