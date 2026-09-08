from __future__ import annotations

import pytest

from app.selection.direction_service import aggregate_compatible_metrics
from app.selection.scoring import (
    DirectionMetrics,
    MetricComponent,
    score_direction,
)


def test_fixed_weights_and_decision_thresholds():
    result = score_direction(
        DirectionMetrics(
            demand=85,
            competition=65,
            profit=88,
            trend=80,
            differentiation=67,
            quality=80,
            coverage=1.0,
        )
    )

    assert result.total == 78
    assert result.decision == "recommended"
    assert result.weights == {
        "demand": 20,
        "competition": 20,
        "profit": 25,
        "trend": 10,
        "differentiation": 15,
        "quality": 10,
    }


@pytest.mark.parametrize(
    ("score", "decision"),
    [(75, "recommended"), (74, "cautious"), (55, "cautious"), (54, "not_recommended")],
)
def test_decision_threshold_boundaries(score, decision):
    result = score_direction(
        DirectionMetrics(
            demand=score,
            competition=score,
            profit=score,
            trend=score,
            differentiation=score,
            quality=score,
            coverage=1.0,
        )
    )

    assert result.total == score
    assert result.decision == decision


def test_low_coverage_blocks_recommendation():
    result = score_direction(
        DirectionMetrics(
            demand=100,
            competition=100,
            profit=100,
            trend=100,
            differentiation=100,
            quality=69,
            coverage=0.69,
        )
    )

    assert result.decision == "needs_data"


def test_unsupported_component_is_omitted_and_reduces_coverage():
    result = score_direction(
        DirectionMetrics(
            demand=(
                MetricComponent(value=90, comparable_values=(10, 90, 100), weight=60),
                MetricComponent(value=None, comparable_values=(), weight=40, supported=False),
            ),
            competition=80,
            profit=80,
            trend=80,
            differentiation=80,
            quality=80,
            coverage=1.0,
        )
    )

    assert result.dimensions["demand"] == 50
    assert result.coverage == pytest.approx(0.88)


def test_percentile_normalization_and_competition_inverse():
    result = score_direction(
        DirectionMetrics(
            demand=(MetricComponent(30, (10, 20, 30), 100),),
            competition=(MetricComponent(30, (10, 20, 30), 100, favorable=False),),
            profit=50,
            trend=50,
            differentiation=50,
            quality=50,
            coverage=1.0,
        )
    )

    assert result.dimensions["demand"] == 100
    assert result.dimensions["competition"] == 0


def test_entire_missing_dimension_is_unscorable():
    result = score_direction(
        DirectionMetrics(
            demand=(MetricComponent(None, (), 100, supported=False),),
            competition=80,
            profit=80,
            trend=80,
            differentiation=80,
            quality=80,
            coverage=1.0,
        )
    )

    assert result.total is None
    assert result.decision == "needs_data"
    assert result.dimensions["demand"] is None


def test_incompatible_period_or_unit_stays_separate_with_warning():
    result = aggregate_compatible_metrics(
        [
            {"metric": "search_volume", "value": 100, "period": "2026-06", "unit": "monthly", "source_id": "a"},
            {"metric": "search_volume", "value": 50, "period": "2026-06", "unit": "monthly", "source_id": "b"},
            {"metric": "search_volume", "value": 7, "period": "2026-W27", "unit": "weekly", "source_id": "c"},
        ]
    )

    assert [series["value"] for series in result.series] == [150, 7]
    assert len(result.warnings) == 1
    assert "周期或单位不兼容" in result.warnings[0]
