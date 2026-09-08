"""产品方向的确定性评分规则。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeAlias


WEIGHTS = {
    "demand": 20,
    "competition": 20,
    "profit": 25,
    "trend": 10,
    "differentiation": 15,
    "quality": 10,
}


@dataclass(frozen=True, slots=True)
class MetricComponent:
    value: float | None
    comparable_values: tuple[float, ...]
    weight: float
    favorable: bool = True
    supported: bool = True


DimensionValue: TypeAlias = float | int | tuple[MetricComponent, ...]


@dataclass(frozen=True, slots=True)
class DirectionMetrics:
    demand: DimensionValue
    competition: DimensionValue
    profit: DimensionValue
    trend: DimensionValue
    differentiation: DimensionValue
    quality: DimensionValue
    coverage: float = 1.0


@dataclass(frozen=True, slots=True)
class ScoreResult:
    total: int | None
    decision: str
    dimensions: dict[str, int | None]
    coverage: float
    weights: dict[str, int] = field(default_factory=lambda: dict(WEIGHTS))


def score_direction(metrics: DirectionMetrics) -> ScoreResult:
    """按固定权重评分；缺失整维时不输出伪精确总分。"""
    dimensions: dict[str, int | None] = {}
    unsupported_fraction = 0.0
    for name in WEIGHTS:
        score, missing = _dimension_score(getattr(metrics, name))
        dimensions[name] = score
        unsupported_fraction += missing

    coverage = max(0.0, min(1.0, metrics.coverage * (1 - unsupported_fraction * 0.3)))
    if any(value is None for value in dimensions.values()):
        return ScoreResult(None, "needs_data", dimensions, coverage)

    total = round(sum(dimensions[name] * weight for name, weight in WEIGHTS.items()) / 100)
    if coverage < 0.70:
        decision = "needs_data"
    elif total >= 75:
        decision = "recommended"
    elif total >= 55:
        decision = "cautious"
    else:
        decision = "not_recommended"
    return ScoreResult(total, decision, dimensions, coverage)


def _dimension_score(value: DimensionValue) -> tuple[int | None, float]:
    if isinstance(value, (int, float)):
        return round(max(0.0, min(100.0, float(value)))), 0.0

    supported = [item for item in value if item.supported and item.value is not None]
    total_weight = sum(max(0.0, item.weight) for item in value)
    supported_weight = sum(max(0.0, item.weight) for item in supported)
    missing = 1.0 if total_weight <= 0 else 1 - supported_weight / total_weight
    if not supported or supported_weight <= 0:
        return None, missing

    weighted = sum(_component_score(item) * max(0.0, item.weight) for item in supported)
    return round(weighted / supported_weight), missing


def _component_score(component: MetricComponent) -> float:
    comparable = sorted(component.comparable_values)
    if not comparable:
        return max(0.0, min(100.0, float(component.value)))
    if len(comparable) == 1:
        percentile = 100.0
    else:
        below = sum(item < float(component.value) for item in comparable)
        equal = sum(item == float(component.value) for item in comparable)
        rank = below + max(0.0, (equal - 1) / 2)
        percentile = 100.0 * rank / (len(comparable) - 1)
    return percentile if component.favorable else 100.0 - percentile
