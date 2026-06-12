from __future__ import annotations


def default_cpi_weights() -> dict[str, float]:
    return {
        "energy": 0.07,
        "gasoline": 0.035,
        "food": 0.13,
        "shelter": 0.34,
        "core_goods": 0.20,
        "core_services_ex_shelter": 0.225,
    }
