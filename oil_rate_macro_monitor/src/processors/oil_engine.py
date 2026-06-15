from __future__ import annotations

import numpy as np
import pandas as pd


FRED_PRICE_COLUMNS = {
    "DCOILWTICO": "wti",
    "DCOILBRENTEU": "brent",
}

EIA_VALUE_COLUMNS = {
    "WCESTUS1": "crude_inventory",
    "WGTSTUS1": "gasoline_inventory",
    "WDISTUS1": "distillate_inventory",
    "WCRFPUS2": "crude_production",
    "WCRRIUS2": "refinery_crude_inputs",
    "WCREXUS2": "crude_exports",
    "WGFUPUS2": "gasoline_product_supplied",
    "WDIUPUS2": "distillate_product_supplied",
    "WKJUPUS2": "jet_fuel_product_supplied",
    "EMM_EPMR_PTE_NUS_DPG": "gasoline_price",
    "EMD_EPD2D_PTE_NUS_DPG": "diesel_price",
    "EER_EPD2F_PF4_Y35NY_DPG": "heating_oil_price",
    "PET.WPULEUS3.W": "refinery_utilization",
}

PRODUCT_DEMAND_WEAK_SIGNALS = {
    "demand_weakening",
    "broad_product_demand_softening",
    "product_demand_softening_with_elevated_cracks",
}


def build_oil_frame(fred_data: pd.DataFrame, eia_data: pd.DataFrame) -> pd.DataFrame:
    prices = _build_fred_price_frame(fred_data)
    eia = _build_eia_weekly_frame(eia_data)
    if prices.empty and eia.empty:
        return pd.DataFrame()
    if prices.empty:
        combined = eia.copy()
    elif eia.empty:
        combined = prices.copy()
    else:
        combined = pd.merge(prices, eia, on="date", how="outer").sort_values("date")
    combined = combined.reset_index(drop=True)
    combined = _ffill_data_columns(combined)
    combined = _calculate_oil_metrics(combined)
    return combined


def _build_fred_price_frame(fred_data: pd.DataFrame) -> pd.DataFrame:
    if fred_data.empty:
        return pd.DataFrame(columns=["date", "wti", "brent"])
    df = fred_data[fred_data["series_id"].isin(FRED_PRICE_COLUMNS)].copy()
    if df.empty:
        return pd.DataFrame(columns=["date", "wti", "brent"])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    pivot = df.pivot_table(index="date", columns="series_id", values="value", aggfunc="last").reset_index()
    pivot = pivot.rename(columns=FRED_PRICE_COLUMNS).sort_values("date").reset_index(drop=True)
    for column in FRED_PRICE_COLUMNS.values():
        if column not in pivot.columns:
            pivot[column] = np.nan
        pivot[f"{column}_asof_date"] = _asof_dates(pivot["date"], pivot[column])
        pivot[column] = pivot[column].ffill()
    return pivot


def _build_eia_weekly_frame(eia_data: pd.DataFrame) -> pd.DataFrame:
    if eia_data.empty:
        return pd.DataFrame(columns=["date"])
    df = eia_data[eia_data["series_id"].isin(EIA_VALUE_COLUMNS)].copy()
    if df.empty:
        return pd.DataFrame(columns=["date"])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    value_pivot = df.pivot_table(index="date", columns="series_id", values="value", aggfunc="last").reset_index()
    unit_pivot = df.pivot_table(index="date", columns="series_id", values="units", aggfunc="last").reset_index()
    value_pivot = value_pivot.rename(columns=EIA_VALUE_COLUMNS).sort_values("date").reset_index(drop=True)
    unit_pivot = unit_pivot.rename(columns=EIA_VALUE_COLUMNS).sort_values("date").reset_index(drop=True)
    value_pivot = value_pivot.loc[:, ~value_pivot.columns.duplicated()]
    unit_pivot = unit_pivot.loc[:, ~unit_pivot.columns.duplicated()]
    for column in EIA_VALUE_COLUMNS.values():
        if column not in value_pivot.columns:
            value_pivot[column] = np.nan
        if column not in unit_pivot.columns:
            unit_pivot[column] = pd.NA
        value_pivot[f"{column}_units"] = unit_pivot[column]
        value_pivot[f"{column}_asof_date"] = _asof_dates(value_pivot["date"], value_pivot[column])
    return _calculate_eia_weekly_metrics(value_pivot)


def _calculate_eia_weekly_metrics(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["crude_inventory_4w_change"] = out["crude_inventory"].diff(4)
    out["gasoline_inventory_4w_change"] = out["gasoline_inventory"].diff(4)
    out["distillate_inventory_4w_change"] = out["distillate_inventory"].diff(4)
    out["total_inventory_proxy"] = (
        out["crude_inventory"] + out["gasoline_inventory"] + out["distillate_inventory"]
    )
    out["total_inventory_proxy_4w_change"] = out["total_inventory_proxy"].diff(4)
    out["gasoline_product_supplied_4w_change"] = out["gasoline_product_supplied"].diff(4)
    out["distillate_product_supplied_4w_change"] = out["distillate_product_supplied"].diff(4)
    out["jet_fuel_product_supplied_4w_change"] = out["jet_fuel_product_supplied"].diff(4)
    out["refinery_utilization_4w_change"] = out["refinery_utilization"].diff(4)
    out["refinery_crude_inputs_4w_change"] = out["refinery_crude_inputs"].diff(4)
    out["crude_production_4w_change"] = out["crude_production"].diff(4)
    out["crude_exports_4w_change"] = out["crude_exports"].diff(4)
    return out


def _calculate_oil_metrics(df: pd.DataFrame) -> pd.DataFrame:
    out = df.sort_values("date").reset_index(drop=True).copy()
    for column in ["wti", "brent"]:
        if column not in out.columns:
            out[column] = np.nan
    for window in [5, 20, 60]:
        out[f"wti_return_{window}d"] = out["wti"].pct_change(window)
        out[f"brent_return_{window}d"] = out["brent"].pct_change(window)
    out["brent_wti_spread"] = out["brent"] - out["wti"]
    out["gasoline_crack_proxy"] = out["gasoline_price"] * 42 - out["wti"] if "gasoline_price" in out else np.nan
    out["diesel_crack_proxy"] = out["diesel_price"] * 42 - out["wti"] if "diesel_price" in out else np.nan
    out["gasoline_crack_20d_change"] = out["gasoline_crack_proxy"].diff(20)
    out["diesel_crack_20d_change"] = out["diesel_crack_proxy"].diff(20)
    out["gasoline_crack_20d_ma"] = out["gasoline_crack_proxy"].rolling(20, min_periods=1).mean()
    out["diesel_crack_20d_ma"] = out["diesel_crack_proxy"].rolling(20, min_periods=1).mean()
    out["oil_momentum_signal"] = out.apply(_oil_momentum_signal, axis=1)
    out["inventory_signal"] = out.apply(_inventory_signal, axis=1)
    out["product_demand_signal"] = out.apply(_product_demand_signal, axis=1)
    out["refinery_signal"] = out.apply(_refinery_signal, axis=1)
    out["supply_signal"] = out.apply(_supply_signal, axis=1)
    out["curve_state"] = "unknown"
    out["curve_signal"] = "unknown"
    out["price_war_risk"] = out.apply(_price_war_risk, axis=1)
    out["oil_regime"] = out.apply(_oil_regime, axis=1)
    out["oil_price_asof_date"] = _max_datetime_columns(out, ["wti_asof_date", "brent_asof_date"])
    out["eia_inventory_asof_date"] = _max_datetime_columns(
        out,
        [
            "crude_inventory_asof_date",
            "gasoline_inventory_asof_date",
            "distillate_inventory_asof_date",
            "refinery_utilization_asof_date",
            "crude_exports_asof_date",
            "crude_production_asof_date",
        ],
    )
    return out


def _ffill_data_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.sort_values("date").reset_index(drop=True).copy()
    for column in out.columns:
        if column == "date":
            continue
        if column.endswith("_asof_date") or column.endswith("_units") or pd.api.types.is_numeric_dtype(out[column]):
            out[column] = out[column].ffill()
    return out


def _oil_momentum_signal(row: pd.Series) -> str:
    ret_5d = row.get("wti_return_5d", np.nan)
    ret_20d = row.get("wti_return_20d", np.nan)
    if pd.notna(ret_5d) and ret_5d > 0.03:
        return "oil_up_short_term"
    if pd.notna(ret_20d) and ret_20d > 0.05:
        return "oil_up_medium_term"
    if pd.notna(ret_20d) and ret_20d < -0.05:
        return "oil_down_medium_term"
    if pd.notna(ret_20d) and abs(ret_20d) <= 0.05:
        return "oil_flat"
    return "unknown"


def _inventory_signal(row: pd.Series) -> str:
    crude = row.get("crude_inventory_4w_change", np.nan)
    gasoline = row.get("gasoline_inventory_4w_change", np.nan)
    distillate = row.get("distillate_inventory_4w_change", np.nan)
    total = row.get("total_inventory_proxy_4w_change", np.nan)
    if pd.notna(crude) and crude > 0 and ((pd.notna(gasoline) and gasoline < 0) or (pd.notna(distillate) and distillate < 0)):
        return "product_tight_crude_loose"
    if pd.notna(crude) and crude < 0 and ((pd.notna(gasoline) and gasoline > 0) or (pd.notna(distillate) and distillate > 0)):
        return "crude_tight_product_loose"
    if pd.notna(total) and total < 0:
        return "inventory_tightening"
    if pd.notna(total) and total > 0:
        return "inventory_building"
    return "mixed"


def _product_demand_signal(row: pd.Series) -> str:
    gasoline_supply = row.get("gasoline_product_supplied_4w_change", np.nan)
    distillate_supply = row.get("distillate_product_supplied_4w_change", np.nan)
    jet_supply = row.get("jet_fuel_product_supplied_4w_change", np.nan)
    gasoline_crack = row.get("gasoline_crack_20d_change", np.nan)
    diesel_crack = row.get("diesel_crack_20d_change", np.nan)
    product_supplied_changes = [gasoline_supply, distillate_supply, jet_supply]
    if all(pd.notna(value) and value < 0 for value in product_supplied_changes):
        if _has_elevated_crack_level(row):
            return "product_demand_softening_with_elevated_cracks"
        return "broad_product_demand_softening"
    if pd.notna(gasoline_supply) and gasoline_supply > 0 and pd.notna(gasoline_crack) and gasoline_crack > 0:
        return "product_demand_gasoline_led"
    if pd.notna(distillate_supply) and distillate_supply > 0 and pd.notna(diesel_crack) and diesel_crack > 0:
        return "product_demand_diesel_led"
    if pd.notna(jet_supply) and jet_supply > 0 and (pd.isna(gasoline_supply) or gasoline_supply <= 0) and (pd.isna(distillate_supply) or distillate_supply <= 0):
        return "jet_recovery"
    if (
        pd.notna(gasoline_supply)
        and pd.notna(distillate_supply)
        and pd.notna(gasoline_crack)
        and pd.notna(diesel_crack)
        and gasoline_supply < 0
        and distillate_supply < 0
        and gasoline_crack < 0
        and diesel_crack < 0
    ):
        return "demand_weakening"
    return "mixed_product_demand"


def _has_elevated_crack_level(row: pd.Series) -> bool:
    gasoline_crack = row.get("gasoline_crack_proxy", np.nan)
    diesel_crack = row.get("diesel_crack_proxy", np.nan)
    return (pd.notna(gasoline_crack) and abs(gasoline_crack) >= 25.0) or (
        pd.notna(diesel_crack) and abs(diesel_crack) >= 25.0
    )


def _refinery_signal(row: pd.Series) -> str:
    utilization = row.get("refinery_utilization", np.nan)
    utilization_change = row.get("refinery_utilization_4w_change", np.nan)
    inputs_change = row.get("refinery_crude_inputs_4w_change", np.nan)
    if pd.notna(utilization) and utilization > 90 and (pd.isna(inputs_change) or inputs_change >= 0):
        return "refinery_strong"
    if pd.notna(utilization_change) and pd.notna(inputs_change) and utilization_change < 0 and inputs_change < 0:
        return "refinery_slowing"
    return "mixed"


def _supply_signal(row: pd.Series) -> str:
    production_change = row.get("crude_production_4w_change", np.nan)
    export_change = row.get("crude_exports_4w_change", np.nan)
    if pd.notna(production_change) and production_change > 0:
        if pd.notna(export_change) and export_change > 0:
            return "us_supply_expanding_export_pressure"
        return "us_supply_expanding"
    if pd.notna(production_change) and abs(production_change) <= 50:
        return "us_supply_flat"
    return "mixed"


def _price_war_risk(row: pd.Series) -> str:
    inventory_building = row.get("inventory_signal") == "inventory_building"
    crack_down = (row.get("gasoline_crack_20d_change", np.nan) < 0) or (row.get("diesel_crack_20d_change", np.nan) < 0)
    exports_rising = row.get("crude_exports_4w_change", np.nan) > 0
    oil_down = row.get("oil_momentum_signal") == "oil_down_medium_term"
    score = sum(bool(item) for item in [inventory_building, crack_down, exports_rising, oil_down])
    if score >= 3:
        return "high"
    if score == 2:
        return "medium"
    if score == 1:
        return "low"
    return "unknown"


def _oil_regime(row: pd.Series) -> str:
    oil_signal = row.get("oil_momentum_signal")
    inventory_signal = row.get("inventory_signal")
    demand_signal = row.get("product_demand_signal")
    supply_signal = row.get("supply_signal")
    price_war = row.get("price_war_risk")
    if oil_signal in {"oil_up_medium_term", "oil_up_short_term"} and demand_signal in {"product_demand_gasoline_led", "product_demand_diesel_led"} and inventory_signal != "inventory_building":
        return "demand_led_strength"
    if oil_signal in {"oil_up_medium_term", "oil_up_short_term"} and inventory_signal == "inventory_tightening" and supply_signal in {"us_supply_flat", "mixed"} and demand_signal not in PRODUCT_DEMAND_WEAK_SIGNALS:
        return "supply_led_tightness"
    if inventory_signal == "inventory_tightening" and demand_signal in PRODUCT_DEMAND_WEAK_SIGNALS:
        return "tight_inventory_weak_products"
    if inventory_signal == "inventory_building" and oil_signal == "oil_down_medium_term" and demand_signal in PRODUCT_DEMAND_WEAK_SIGNALS:
        return "inventory_building_weak_demand"
    if price_war == "high":
        return "price_war_risk"
    if row.get("wti_return_5d", np.nan) > 0.05 and inventory_signal == "inventory_tightening":
        return "supply_shock"
    return "neutral_mixed"


def _asof_dates(dates: pd.Series, values: pd.Series) -> pd.Series:
    asof = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns]")
    valid = values.notna()
    asof.loc[valid] = pd.to_datetime(dates.loc[valid], errors="coerce")
    return asof.ffill()


def _max_datetime_columns(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    existing = [column for column in columns if column in df.columns]
    if not existing:
        return pd.Series(pd.NaT, index=df.index)
    return pd.concat([pd.to_datetime(df[column], errors="coerce") for column in existing], axis=1).max(axis=1)
