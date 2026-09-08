"""基于已选关键词完整字段生成产品方向。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.llm import MissingLLMClient
from app.db.models import ProductDirection, ResearchKeyword
from app.selection.repository import SelectionRepository


@dataclass(frozen=True, slots=True)
class AggregationResult:
    series: list[dict[str, Any]]
    warnings: list[str]


def aggregate_compatible_metrics(metrics: list[dict[str, Any]]) -> AggregationResult:
    """仅合并指标名、周期和单位均一致的记录。"""
    groups: dict[tuple[Any, Any, Any], dict[str, Any]] = {}
    order: list[tuple[Any, Any, Any]] = []
    by_metric: dict[Any, set[tuple[Any, Any]]] = {}
    for item in metrics:
        key = (item.get("metric"), item.get("period"), item.get("unit"))
        if key not in groups:
            groups[key] = dict(item) | {"source_ids": [item.get("source_id")]}
            order.append(key)
        else:
            groups[key]["value"] += item.get("value", 0)
            groups[key]["source_ids"].append(item.get("source_id"))
        by_metric.setdefault(key[0], set()).add((key[1], key[2]))
    warnings = [
        f"指标 {metric} 的周期或单位不兼容，已分开保留"
        for metric, variants in by_metric.items() if len(variants) > 1
    ]
    return AggregationResult([groups[key] for key in order], warnings)


class ProductDirectionService:
    """将用户选择的真实关键词字段完整交给 LLM 进行产品方向研究。"""

    def __init__(self, session: Session, llm_client: Any | None) -> None:
        self.session = session
        self.llm_client = llm_client
        self.repository = SelectionRepository(session)

    async def build(self, project_id: int, user_id: str) -> ProductDirection:
        project = self.repository.get_owned_project(project_id, user_id)
        selected = list(self.session.scalars(
            select(ResearchKeyword).where(
                ResearchKeyword.project_id == project.id,
                ResearchKeyword.selected.is_(True),
            ).order_by(ResearchKeyword.id)
        ))
        if not selected:
            raise ValueError("请先选择关键词再构建产品方向")
        if self.llm_client is None or isinstance(self.llm_client, MissingLLMClient):
            raise ValueError("未配置真实 LLM，无法研究产品方向")

        records = [_keyword_evidence(row) for row in selected]
        prompt_data = {
            "marketplace": project.marketplace,
            "selected_keywords": records,
        }
        try:
            raw_response = self.llm_client.generate(_DIRECTION_SYSTEM_PROMPT, json.dumps(
                prompt_data, ensure_ascii=False, default=str
            ))
        except Exception as exc:
            raise ValueError(f"LLM 产品方向研究调用失败：{exc}") from exc

        analysis = _parse_direction_analysis(raw_response, [row.keyword for row in selected])
        cluster = {
            "primary": [analysis["primary_keyword"]],
            "related": [],
            "long_tail": analysis["long_tail_keywords"],
            "scenario": [],
            "all": [row.keyword for row in selected],
        }

        direction = ProductDirection(
            project_id=project.id,
            name=analysis["primary_keyword"],
            keyword_cluster_json=cluster,
            market_metrics_json={
                "llm_research": analysis,
                "llm_input": prompt_data,
                "selected_keyword_records": records,
                "warnings": [],
            },
            field_lineage_json={
                "selected_keywords": [row.field_lineage_json for row in selected],
            },
            competitors_json={},
            data_completeness=1.0,
        )
        self.session.add(direction)
        self.session.commit()
        return direction


_DIRECTION_SYSTEM_PROMPT = """你是亚马逊选品研究助手。根据给定的已选关键词及其全部真实指标，
选择一个主词，用于提高商品标题和广告的点击率；选择若干长尾词，用于描述产品信息。
主词和长尾词必须来自输入的已选关键词。
product_direction 必须用中文写成 3 到 5 句的完整产品方向，覆盖：产品定位、目标用户、核心使用场景、
可从关键词或指标推断的差异化机会，以及标题/卖点应优先表达的信息。仅能依据输入数据作出判断；
材质、功能、认证或合规信息没有数据依据时，必须明确写为“待产品验证”，不得当作事实。
只输出 JSON：
{"primary_keyword":"...","long_tail_keywords":["..."],"product_direction":"..."}"""


def _keyword_evidence(row: ResearchKeyword) -> dict[str, Any]:
    return {
        "id": row.id,
        "keyword": row.keyword,
        "normalized_keyword": row.normalized_keyword,
        "search_volume": row.search_volume,
        "trend_rate": row.trend_rate,
        "trend_period": row.trend_period,
        "product_count": row.product_count,
        "competition_index": row.competition_index,
        "cpc": row.cpc,
        "conversion_rate": row.conversion_rate,
        "relevance_score": row.relevance_score,
        "opportunity_score": row.opportunity_score,
        "metrics": row.metrics_json,
    }


def _parse_direction_analysis(raw_response: str, selected_keywords: list[str]) -> dict[str, Any]:
    content = str(raw_response).strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM 产品方向研究未返回可解析的 JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("LLM 产品方向研究结果格式无效")

    choices = {keyword.casefold(): keyword for keyword in selected_keywords}
    primary = choices.get(str(parsed.get("primary_keyword") or "").strip().casefold())
    long_tail_raw = parsed.get("long_tail_keywords")
    if not primary or not isinstance(long_tail_raw, list):
        raise ValueError("LLM 产品方向研究结果缺少有效主词或长尾词")
    long_tail = list(dict.fromkeys(
        choices[value.casefold()]
        for item in long_tail_raw
        if isinstance(item, str) and (value := item.strip()) and value.casefold() in choices
    ))
    if not long_tail:
        raise ValueError("LLM 产品方向研究未返回已选关键词中的长尾词")
    product_direction = str(parsed.get("product_direction") or "").strip()
    if not product_direction:
        raise ValueError("LLM 产品方向研究结果缺少产品方向")
    return {
        "primary_keyword": primary,
        "long_tail_keywords": long_tail,
        "product_direction": product_direction,
    }
