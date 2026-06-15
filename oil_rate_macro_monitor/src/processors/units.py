from __future__ import annotations

from typing import Any

import pandas as pd


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except Exception:  # noqa: BLE001
        return False


def is_thousand_barrels(units: Any) -> bool:
    if is_missing(units):
        return False
    normalized = str(units).strip().upper()
    return normalized in {"MBBL", "THOUSAND BARRELS"}


def is_thousand_barrels_per_day(units: Any) -> bool:
    if is_missing(units):
        return False
    normalized = str(units).strip().upper()
    return normalized in {"MBBL/D", "MBBL/DAY", "THOUSAND BARRELS PER DAY", "THOUSAND BARRELS/DAY"}


def million_barrels(value: Any, units: Any) -> float | None:
    if is_missing(value) or not is_thousand_barrels(units):
        return None
    return float(value) / 1000.0


def million_barrels_per_day(value: Any, units: Any) -> float | None:
    if is_missing(value) or not is_thousand_barrels_per_day(units):
        return None
    return float(value) / 1000.0
