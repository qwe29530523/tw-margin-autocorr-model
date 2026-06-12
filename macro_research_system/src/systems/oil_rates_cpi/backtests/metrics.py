from __future__ import annotations

import math


def mae(errors: list[float]) -> float:
    return sum(abs(item) for item in errors) / len(errors)


def rmse(errors: list[float]) -> float:
    return math.sqrt(sum(item * item for item in errors) / len(errors))
