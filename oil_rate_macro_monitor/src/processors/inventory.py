from __future__ import annotations

import numpy as np
import pandas as pd


SERIES_TO_COLUMN = {
    "WCESTUS1": "crude_inventory",
    "PET.WCESTUS1.W": "crude_inventory",
    "WGTSTUS1": "gasoline_inventory",
    "PET.WGTSTUS1.W": "gasoline_inventory",
    "WDISTUS1": "distillate_inventory",
    "PET.WDISTUS1.W": "distillate_inventory",
    "WCRFPUS2": "crude_production",
    "PET.WCRFPUS2.W": "crude_production",
    "WCRRIUS2": "refiner_inputs",
    "PET.WCRRIUS2.W": "refiner_inputs",
    "WCREXUS2": "crude_exports",
    "PET.WCREXUS2.W": "crude_exports",
    "PET.WPULEUS3.W": "refinery_utilization",
}

INVENTORY_BASE_COLUMNS = [
    "crude_inventory",
    "gasoline_inventory",
    "distillate_inventory",
    "crude_production",
    "refiner_inputs",
    "crude_exports",
    "refinery_utilization",
]

INVENTORY_COLUMNS = [
    "date",
    *INVENTORY_BASE_COLUMNS,
    "crude_inventory_units",
    "gasoline_inventory_units",
    "distillate_inventory_units",
    "crude_production_units",
    "refiner_inputs_units",
    "crude_exports_units",
    "refinery_utilization_units",
    "crude_inventory_4w_change",
    "gasoline_inventory_4w_change",
    "distillate_inventory_4w_change",
    "total_petroleum_inventory_proxy",
    "total_petroleum_inventory_proxy_4w_change",
    "refinery_utilization_4w_change",
    "crude_exports_4w_change",
    "crude_production_4w_change",
    "inventory_signal",
]


def process_inventory(eia_data: pd.DataFrame) -> pd.DataFrame:
    if eia_data.empty:
        return pd.DataFrame(columns=INVENTORY_COLUMNS)
    df = eia_data.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    pivot = df.pivot_table(index="date", columns="series_id", values="value", aggfunc="last").reset_index()
    unit_pivot = df.pivot_table(index="date", columns="series_id", values="units", aggfunc="last").reset_index()
    pivot = pivot.rename(columns=SERIES_TO_COLUMN).sort_values("date").reset_index(drop=True)
    unit_pivot = unit_pivot.rename(columns=SERIES_TO_COLUMN).sort_values("date").reset_index(drop=True)
    pivot = pivot.loc[:, ~pivot.columns.duplicated()]
    unit_pivot = unit_pivot.loc[:, ~unit_pivot.columns.duplicated()]
    for column in INVENTORY_BASE_COLUMNS:
        if column not in pivot.columns:
            pivot[column] = np.nan
        if column not in unit_pivot.columns:
            unit_pivot[column] = pd.NA

    out = pivot[["date", *INVENTORY_BASE_COLUMNS]].copy()
    for column in INVENTORY_BASE_COLUMNS:
        out[f"{column}_units"] = unit_pivot[column]
    out["crude_inventory_4w_change"] = out["crude_inventory"].diff(4)
    out["gasoline_inventory_4w_change"] = out["gasoline_inventory"].diff(4)
    out["distillate_inventory_4w_change"] = out["distillate_inventory"].diff(4)
    out["total_petroleum_inventory_proxy"] = (
        out["crude_inventory"] + out["gasoline_inventory"] + out["distillate_inventory"]
    )
    out["total_petroleum_inventory_proxy_4w_change"] = out["total_petroleum_inventory_proxy"].diff(4)
    out["refinery_utilization_4w_change"] = out["refinery_utilization"].diff(4)
    out["crude_exports_4w_change"] = out["crude_exports"].diff(4)
    out["crude_production_4w_change"] = out["crude_production"].diff(4)

    out["inventory_signal"] = out.apply(_inventory_signal, axis=1)
    return out


def _inventory_signal(row: pd.Series) -> str:
    total_change = row.get("total_petroleum_inventory_proxy_4w_change", np.nan)
    refinery_change = row.get("refinery_utilization_4w_change", np.nan)
    crude_change = row.get("crude_inventory_4w_change", np.nan)
    gasoline_change = row.get("gasoline_inventory_4w_change", np.nan)
    distillate_change = row.get("distillate_inventory_4w_change", np.nan)

    if pd.notna(crude_change) and crude_change > 0 and (
        (pd.notna(gasoline_change) and gasoline_change < 0)
        or (pd.notna(distillate_change) and distillate_change < 0)
    ):
        return "product_tight_crude_loose"
    if pd.notna(crude_change) and crude_change < 0 and (
        (pd.notna(gasoline_change) and gasoline_change > 0)
        or (pd.notna(distillate_change) and distillate_change > 0)
    ):
        return "crude_tight_product_loose"
    if pd.notna(total_change) and total_change < 0 and (pd.isna(refinery_change) or refinery_change >= 0):
        return "inventory_tightening"
    if pd.notna(total_change) and total_change > 0:
        return "inventory_building"
    return "mixed"
