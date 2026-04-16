"""Signal score helpers for v2 strategies."""

from __future__ import annotations


def clip_score(score: float, *, lower: float = 0.0, upper: float = 100.0) -> float:
    if lower > upper:
        raise ValueError("lower bound must not exceed upper bound")
    return max(lower, min(upper, float(score)))


def weighted_score(*components: tuple[float, float]) -> float:
    total = 0.0
    for value, weight in components:
        total += float(value) * float(weight)
    return total
