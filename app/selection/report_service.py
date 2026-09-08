"""选品决策报告：规则评分负责事实，真实 LLM 仅负责解释。"""
from __future__ import annotations

import json
import math
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.llm import MissingLLMClient
from app.db.models import (
    PricingSnapshot,
    ProductDirection,
    SelectionReport,
    SourceSnapshot,
)
from app.selection.repository import SelectionRepository
from app.selection.scoring import DirectionMetrics, ScoreResult, score_direction


_REPORT_FIELDS = {"summary", "findings", "risks", "actions"}
_SCORE_FIELDS = (
    "demand",
    "competition",
    "profit",
    "trend",
    "differentiation",
    "quality",
)


class ReportService:
    def __init__(self, *, session: Session, llm_client: Any | None) -> None:
        self.session = session
        self.llm_client = llm_client
        self.repository = SelectionRepository(session)

    def generate(self, project_id: int, user_id: str) -> SelectionReport:
        project = self.repository.get_owned_project(project_id, user_id)
        direction = self.session.scalar(
            select(ProductDirection)
            .where(ProductDirection.project_id == project.id)
            .order_by(ProductDirection.created_at.desc(), ProductDirection.id.desc())
        )
        pricing = self.session.scalar(
            select(PricingSnapshot)
            .where(PricingSnapshot.project_id == project.id)
            .order_by(PricingSnapshot.calculated_at.desc(), PricingSnapshot.id.desc())
        )
        if direction is None:
            raise ValueError("请先完成产品方向研究")
        if pricing is None:
            raise ValueError("请先完成成本与定价")

        score = _score_from_direction(direction)
        evidence = _build_evidence(self.session, direction, pricing, score)
        risk_payload = {
            "warnings": list((direction.market_metrics_json or {}).get("warnings", [])),
            "missing_fields": evidence["missing_fields"],
        }
        llm_status = "unavailable"
        llm_report = None

        if score.total is not None and self.llm_client is not None and not isinstance(
            self.llm_client, MissingLLMClient
        ):
            try:
                raw = self.llm_client.generate(
                    _SYSTEM_PROMPT,
                    json.dumps(_prompt_payload(project, direction, pricing, score, evidence), ensure_ascii=False),
                )
                llm_report = _parse_llm_report(raw)
                llm_status = "succeeded"
            except Exception:
                llm_status = "failed"
                llm_report = None
                risk_payload["llm_error"] = "真实 LLM 调用或结果解析失败"

        report = SelectionReport(
            project_id=project.id,
            score_total=score.total,
            score_dimensions_json={
                "dimensions": score.dimensions,
                "weights": score.weights,
                "coverage": score.coverage,
            },
            decision=score.decision,
            evidence_json=evidence,
            risks_json=risk_payload,
            llm_status=llm_status,
            llm_report=llm_report,
        )
        self.session.add(report)
        self.session.commit()
        return report


def _score_from_direction(direction: ProductDirection) -> ScoreResult:
    raw = (direction.market_metrics_json or {}).get("rule_metrics")
    if not isinstance(raw, dict):
        return _needs_data_score(direction.data_completeness)
    values: dict[str, float] = {}
    for name in _SCORE_FIELDS:
        value = raw.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return _needs_data_score(direction.data_completeness)
        number = float(value)
        if not math.isfinite(number) or not 0 <= number <= 100:
            return _needs_data_score(direction.data_completeness)
        values[name] = number
    coverage = raw.get("coverage", direction.data_completeness)
    if isinstance(coverage, bool) or not isinstance(coverage, (int, float)):
        return _needs_data_score(direction.data_completeness)
    coverage_number = float(coverage)
    if not math.isfinite(coverage_number) or not 0 <= coverage_number <= 1:
        return _needs_data_score(direction.data_completeness)
    return score_direction(DirectionMetrics(**values, coverage=coverage_number))


def _needs_data_score(coverage: float | None) -> ScoreResult:
    safe_coverage = float(coverage or 0)
    if not math.isfinite(safe_coverage):
        safe_coverage = 0
    return ScoreResult(
        total=None,
        decision="needs_data",
        dimensions={name: None for name in _SCORE_FIELDS},
        coverage=max(0.0, min(1.0, safe_coverage)),
    )


def _build_evidence(
    session: Session,
    direction: ProductDirection,
    pricing: PricingSnapshot,
    score: ScoreResult,
) -> dict[str, Any]:
    snapshots = list(session.scalars(
        select(SourceSnapshot)
        .where(SourceSnapshot.project_id == direction.project_id)
        .order_by(SourceSnapshot.collected_at.desc(), SourceSnapshot.id.desc())
    ))
    sources = []
    seen = set()
    for snapshot in snapshots:
        key = (snapshot.source_id, snapshot.capability, snapshot.tool_name)
        if key in seen:
            continue
        seen.add(key)
        sources.append({
            "source_id": snapshot.source_id,
            "capability": snapshot.capability,
            "tool_name": snapshot.tool_name,
            "collected_at": snapshot.collected_at.isoformat(),
            "snapshot_id": snapshot.id,
        })
    missing = [name for name, value in score.dimensions.items() if value is None]
    return {
        "direction_id": direction.id,
        "pricing_snapshot_id": pricing.id,
        "keyword_cluster": direction.keyword_cluster_json or {},
        "score": {
            "total": score.total,
            "decision": score.decision,
            "dimensions": score.dimensions,
            "weights": score.weights,
            "coverage": score.coverage,
        },
        "pricing": _pricing_evidence(pricing),
        "sources": sources,
        "missing_fields": missing,
    }


def _pricing_evidence(pricing: PricingSnapshot) -> dict[str, Any]:
    return {
        "source_currency": pricing.source_currency,
        "target_price": _decimal_text(pricing.target_price),
        "international_shipping": _decimal_text(pricing.international_shipping),
        "commission_amount": _decimal_text(pricing.commission_amount),
        "net_profit_amount": _decimal_text(pricing.net_profit_amount),
        "commission_rate": _decimal_text(pricing.commission_rate),
        "target_net_margin": _decimal_text(pricing.target_net_margin),
        "freight_template_snapshot": pricing.freight_template_snapshot_json,
        "exchange_rate_snapshot": pricing.exchange_rate_snapshot_json,
    }


def _prompt_payload(project, direction, pricing, score, evidence) -> dict[str, Any]:
    return {
        "project": {
            "name": project.name,
            "marketplace": project.marketplace,
            "target_currency": project.target_currency,
        },
        "direction": {
            "name": direction.name,
            "keyword_cluster": direction.keyword_cluster_json or {},
        },
        "fixed_rule_score": {
            "total": score.total,
            "decision": score.decision,
            "dimensions": score.dimensions,
            "weights": score.weights,
            "coverage": score.coverage,
        },
        "pricing": _pricing_evidence(pricing),
        "source_summaries": evidence["sources"],
        "risks": (direction.market_metrics_json or {}).get("warnings", []),
        "missing_fields": evidence["missing_fields"],
    }


def _parse_llm_report(raw: str) -> dict[str, Any]:
    text = str(raw).strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1])
            if text.lstrip().startswith("json"):
                text = text.lstrip()[4:].lstrip()
    payload = json.loads(text)
    if not isinstance(payload, dict) or set(payload) != _REPORT_FIELDS:
        raise ValueError("LLM 报告字段不完整")
    if not isinstance(payload["summary"], str) or not payload["summary"].strip():
        raise ValueError("LLM 报告摘要无效")
    for name in ("findings", "risks", "actions"):
        if not isinstance(payload[name], list) or any(not isinstance(item, str) for item in payload[name]):
            raise ValueError("LLM 报告列表字段无效")
    return {name: payload[name] for name in ("summary", "findings", "risks", "actions")}


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


_SYSTEM_PROMPT = """你是亚马逊选品报告解释器。规则引擎给出的分数、权重、结论和定价是唯一事实源。
不得重新计算或修改分数，不得推测缺失字段，不得编造市场数据或来源。
只返回 JSON 对象，且只能包含 summary、findings、risks、actions 四个字段；后三个字段必须是字符串数组。"""
