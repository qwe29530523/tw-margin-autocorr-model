from __future__ import annotations


def assert_no_future_actual(available_date: str, target_date: str) -> bool:
    return available_date <= target_date
