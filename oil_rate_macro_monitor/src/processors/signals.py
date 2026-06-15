from __future__ import annotations

from typing import Any

import pandas as pd

from src.processors.macro_regime_engine import build_macro_summary


STRONG_CRACKS = {"industrial_logistics_strength", "driving_season_strength"}
TIGHT_INVENTORY = {"inventory_tightening", "product_tight_crude_loose", "crude_tight_product_loose", "supply_shock"}
RATES_UP = {"rates_up", "curve_bear_steepening"}
RATES_DOWN = {"rates_down", "curve_bull_steepening"}


def generate_macro_regime(
    oil_20d_return: float | None,
    oil_5d_return: float | None,
    crack_signal: str,
    inventory_signal: str,
    rate_signal: str,
    usd_trend: str = "mixed",
) -> dict[str, Any]:
    oil_20d = _num(oil_20d_return)
    oil_5d = _num(oil_5d_return)
    crack_signal = crack_signal or "mixed"
    inventory_signal = inventory_signal or "mixed"
    rate_signal = rate_signal or "mixed"
    reasons: list[str] = []
    warnings: list[str] = []

    if oil_20d > 0.05 and rate_signal in RATES_UP and crack_signal == "industrial_logistics_strength" and inventory_signal == "inventory_tightening":
        regime = "inflation_pressure"
        reasons.extend(["油價 20D 漲幅大於 5%", "利率上行", "柴油裂解價差偏強", "庫存收緊"])
    elif oil_20d < -0.05 and rate_signal in RATES_DOWN and crack_signal == "demand_weakening" and inventory_signal == "inventory_building":
        regime = "recession_pressure"
        reasons.extend(["油價 20D 跌幅大於 5%", "利率下行", "裂解價差轉弱", "庫存累積"])
    elif oil_5d > 0.05 and inventory_signal in TIGHT_INVENTORY:
        regime = "supply_shock"
        reasons.extend(["油價 5D 快速上漲", "庫存或供給訊號偏緊"])
    elif oil_20d > 0.05 and rate_signal in RATES_UP and crack_signal in STRONG_CRACKS and inventory_signal != "inventory_building":
        regime = "growth_strength"
        reasons.extend(["油價上漲", "利率或曲線反映成長", "產品需求訊號偏強"])
    elif oil_20d > 0 and rate_signal in RATES_DOWN and crack_signal in {"mixed", "demand_weakening"} and inventory_signal in TIGHT_INVENTORY:
        regime = "stagflation_risk"
        reasons.extend(["油價上漲但利率下行", "需求訊號不一致", "庫存或供給偏緊"])
    else:
        regime = "neutral_mixed"
        reasons.append("油價、利率、庫存與裂解價差沒有形成單一明確 regime")

    secondary_regime = derive_secondary_regime(inventory_signal, crack_signal)

    if usd_trend == "usd_up":
        warnings.append("美元走強可能壓抑油價風險偏好。")
    if rate_signal == "inversion_pressure":
        warnings.append("殖利率曲線倒掛壓力仍在，需留意成長下修風險。")

    confidence_score = min(100, 45 + 12 * len(reasons) + 5 * len(warnings))
    return {
        "regime": regime,
        "secondary_regime": secondary_regime,
        "confidence_score": confidence_score,
        "reasons": reasons,
        "warnings": warnings,
    }


def derive_secondary_regime(inventory_signal: str, crack_signal: str) -> str:
    if inventory_signal == "inventory_tightening" and crack_signal == "demand_weakening":
        return "tight_inventory_weak_products"
    return "none"


def generate_macro_regime_from_frames(
    oil_curve: pd.DataFrame,
    crack_spreads: pd.DataFrame,
    inventory: pd.DataFrame,
    rates: pd.DataFrame,
    usd_trend: str = "mixed",
) -> dict[str, Any]:
    if "oil_regime" in oil_curve.columns or "rates_regime" in rates.columns:
        return build_macro_summary(oil_curve, rates, yahoo_overlay=False)
    oil_latest = _latest(oil_curve)
    crack_latest = _latest(crack_spreads)
    inventory_latest = _latest(inventory)
    rates_latest = _latest(rates)
    result = generate_macro_regime(
        oil_20d_return=oil_latest.get("wti_return_20d"),
        oil_5d_return=oil_latest.get("wti_return_5d"),
        crack_signal=str(crack_latest.get("crack_signal", "mixed")),
        inventory_signal=str(inventory_latest.get("inventory_signal", "mixed")),
        rate_signal=str(rates_latest.get("rate_signal", "mixed")),
        usd_trend=usd_trend,
    )
    rate_data_incomplete = _missing(rates_latest.get("ten_year")) or _missing(rates_latest.get("two_year"))
    if rate_data_incomplete:
        result["confidence_score"] = max(0, int(result["confidence_score"]) - 20)
        _append_warning(
            result,
            "Rates data incomplete; using latest valid observation or lowering confidence.",
        )
    if oil_latest.get("curve_state", "unknown") == "unknown":
        _append_warning(
            result,
            "Curve state unknown; complete term structure requires CME/ICE/Nasdaq Data Link or another futures curve source.",
        )

    result["metrics"] = {
        "date": _date_value(oil_latest, crack_latest, inventory_latest, rates_latest),
        "oil_price_asof_date": _row_date(oil_latest),
        "crack_spread_asof_date": _row_date(crack_latest),
        "eia_inventory_asof_date": _row_date(inventory_latest),
        "fred_rates_asof_date": _rates_asof_text(rates_latest),
        "wti": oil_latest.get("wti"),
        "brent": oil_latest.get("brent"),
        "brent_wti_spread": oil_latest.get("brent_wti_spread"),
        "wti_return_5d": oil_latest.get("wti_return_5d"),
        "wti_return_20d": oil_latest.get("wti_return_20d"),
        "wti_return_60d": oil_latest.get("wti_return_60d"),
        "curve_state": oil_latest.get("curve_state", "unknown"),
        "gasoline_crack": crack_latest.get("gasoline_crack"),
        "diesel_crack": crack_latest.get("diesel_crack"),
        "gasoline_crack_20d_change": crack_latest.get("gasoline_crack_20d_change"),
        "diesel_crack_20d_change": crack_latest.get("diesel_crack_20d_change"),
        "gasoline_crack_20d_ma": crack_latest.get("gasoline_crack_20d_ma"),
        "diesel_crack_20d_ma": crack_latest.get("diesel_crack_20d_ma"),
        "crack_signal": crack_latest.get("crack_signal", "mixed"),
        "crude_inventory_4w_change": inventory_latest.get("crude_inventory_4w_change"),
        "gasoline_inventory_4w_change": inventory_latest.get("gasoline_inventory_4w_change"),
        "distillate_inventory_4w_change": inventory_latest.get("distillate_inventory_4w_change"),
        "refinery_utilization": inventory_latest.get("refinery_utilization"),
        "crude_exports": inventory_latest.get("crude_exports"),
        "crude_exports_units": inventory_latest.get("crude_exports_units"),
        "crude_production": inventory_latest.get("crude_production"),
        "crude_production_units": inventory_latest.get("crude_production_units"),
        "crude_inventory_units": inventory_latest.get("crude_inventory_units"),
        "gasoline_inventory_units": inventory_latest.get("gasoline_inventory_units"),
        "distillate_inventory_units": inventory_latest.get("distillate_inventory_units"),
        "inventory_signal": inventory_latest.get("inventory_signal", "mixed"),
        "ten_year": rates_latest.get("ten_year"),
        "two_year": rates_latest.get("two_year"),
        "ten_year_asof_date": _date_or_missing(rates_latest.get("ten_year_asof_date")),
        "two_year_asof_date": _date_or_missing(rates_latest.get("two_year_asof_date")),
        "ten_year_two_year_spread_asof_date": _date_or_missing(
            rates_latest.get("ten_year_two_year_spread_asof_date")
        ),
        "ten_year_three_month_spread_asof_date": _date_or_missing(
            rates_latest.get("ten_year_three_month_spread_asof_date")
        ),
        "ten_year_two_year_spread": rates_latest.get("ten_year_two_year_spread"),
        "ten_year_three_month_spread": rates_latest.get("ten_year_three_month_spread"),
        "rate_signal": rates_latest.get("rate_signal", "mixed"),
        "dxy_trend": usd_trend,
    }
    return result


def _latest(df: pd.DataFrame) -> dict[str, Any]:
    if df is None or df.empty:
        return {}
    return df.dropna(how="all").iloc[-1].to_dict()


def _num(value: float | None) -> float:
    if value is None or pd.isna(value):
        return 0.0
    return float(value)


def _missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except Exception:  # noqa: BLE001
        return False


def _append_warning(result: dict[str, Any], warning: str) -> None:
    warnings = result.setdefault("warnings", [])
    if warning not in warnings:
        warnings.append(warning)


def _date_value(*rows: dict[str, Any]) -> str | None:
    dates = [row.get("date") for row in rows if row.get("date") is not None]
    if not dates:
        return None
    return str(max(pd.to_datetime(dates)).date())


def _row_date(row: dict[str, Any]) -> str | None:
    if not row or row.get("date") is None:
        return None
    return str(pd.to_datetime(row.get("date")).date())


def _date_or_missing(value: Any) -> str:
    if _missing(value):
        return "missing"
    return str(pd.to_datetime(value).date())


def _rates_asof_text(row: dict[str, Any]) -> str:
    if not row:
        return "missing"
    return (
        f"10Y {_date_or_missing(row.get('ten_year_asof_date'))} / "
        f"2Y {_date_or_missing(row.get('two_year_asof_date'))} / "
        f"10Y-2Y {_date_or_missing(row.get('ten_year_two_year_spread_asof_date'))} / "
        f"10Y-3M {_date_or_missing(row.get('ten_year_three_month_spread_asof_date'))}"
    )
