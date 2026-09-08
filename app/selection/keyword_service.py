"""项目制关键词调研编排。"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import KeywordResearchRun, ResearchKeyword, SourceSnapshot
from app.selection.contracts import McpCallResult, McpCapability
from app.selection.repository import SelectionRepository


CAPABILITY_BY_INPUT = {
    "seed": McpCapability.KEYWORD_EXPAND,
    "asin": McpCapability.ASIN_KEYWORD_REVERSE,
    "category": McpCapability.CATEGORY_KEYWORDS,
}
_ARGUMENT_BY_INPUT = {"seed": "keyword", "asin": "asin", "category": "category"}
_ASIN_PATTERN = re.compile(r"^[A-Z0-9]{10}$")
_MODEL_FIELDS = {
    "search_volume", "trend_rate", "trend_period", "product_count", "competition_index",
    "cpc", "conversion_rate", "relevance_score", "opportunity_score",
}
_SENSITIVE_PARTS = ("authorization", "api_key", "apikey", "token", "cookie", "secret", "password", "headers")


class IdempotencyConflictError(ValueError):
    """同一幂等键被用于不同请求语义。"""


class KeywordResearchService:
    def __init__(self, session: Session, registry: Any) -> None:
        self.session = session
        self.registry = registry
        self.repository = SelectionRepository(session)

    async def run(
        self,
        project_id: int,
        user_id: str,
        input_type: str,
        input_value: str,
        marketplace: str,
        category: str | None,
        request_id: str,
    ) -> KeywordResearchRun:
        project = self.repository.get_owned_project(project_id, user_id)
        normalized_type, cleaned_value = _validate_input(input_type, input_value)
        cleaned_marketplace = _collapse_spaces(marketplace).upper()
        cleaned_category = _collapse_spaces(category) if category else None
        fingerprint = _fingerprint(
            normalized_type, cleaned_value, cleaned_marketplace, cleaned_category
        )
        existing = self._find_idempotent_run(project_id, request_id)
        if existing is not None:
            if existing.filters_json.get("request_fingerprint") != fingerprint:
                raise IdempotencyConflictError("幂等键已用于不同的关键词调研请求")
            return existing

        run = KeywordResearchRun(
            project_id=project.id,
            input_type=normalized_type,
            input_value=cleaned_value,
            marketplace=cleaned_marketplace,
            category=cleaned_category,
            filters_json={"request_id": request_id, "request_fingerprint": fingerprint},
            status="running",
        )
        self.session.add(run)
        self.session.flush()

        capability = CAPABILITY_BY_INPUT[normalized_type]
        arguments: dict[str, Any] = {
            "marketplace": cleaned_marketplace,
            _ARGUMENT_BY_INPUT[normalized_type]: cleaned_value,
        }
        if cleaned_category and normalized_type != "category":
            arguments["category"] = cleaned_category
        try:
            if hasattr(self.registry, "collect_keywords"):
                results = await self.registry.collect_keywords(
                    normalized_type, cleaned_value, cleaned_marketplace
                )
            else:
                results = await self.registry.call(capability, arguments)
        except Exception:
            results = []

        for result in results:
            self.session.add(_build_snapshot(project.id, run.id, arguments, result))

        successful = [result for result in results if result.status == "succeeded"]
        failed = [result for result in results if result.status != "succeeded"]
        if not successful:
            run.status = "failed"
            warnings = [warning for result in failed for warning in result.warnings]
            run.error_summary = "；".join(warnings) or "所有 MCP 数据源调用失败"
        else:
            rows = _keyword_rows(project.id, run.id, successful)
            self.session.add_all(rows)
            run.status = "partial" if failed else "succeeded"
            if failed:
                run.error_summary = "部分 MCP 数据源调用失败"
        run.completed_at = datetime.now(UTC)
        self.session.commit()
        return run

    def _find_idempotent_run(self, project_id: int, request_id: str) -> KeywordResearchRun | None:
        runs = self.session.scalars(
            select(KeywordResearchRun)
            .where(KeywordResearchRun.project_id == project_id)
            .order_by(KeywordResearchRun.id.desc())
        )
        return next(
            (run for run in runs if run.filters_json.get("request_id") == request_id), None
        )


def normalize_keyword(value: str) -> str:
    return _collapse_spaces(value).casefold()


def _validate_input(input_type: str, input_value: str) -> tuple[str, str]:
    normalized_type = _collapse_spaces(input_type).casefold()
    if normalized_type not in CAPABILITY_BY_INPUT:
        raise ValueError("不支持的关键词调研输入类型")
    cleaned_value = _collapse_spaces(input_value)
    if not cleaned_value:
        raise ValueError("调研输入不能为空")
    if normalized_type == "asin":
        cleaned_value = cleaned_value.upper()
        if not _ASIN_PATTERN.fullmatch(cleaned_value):
            raise ValueError("ASIN 必须是 10 位大写字母或数字")
    return normalized_type, cleaned_value


def _collapse_spaces(value: str) -> str:
    return " ".join(str(value).split())


def _fingerprint(input_type: str, input_value: str, marketplace: str, category: str | None) -> str:
    canonical = {
        "input_type": input_type,
        "input_value": input_value.casefold(),
        "marketplace": marketplace,
        "category": category.casefold() if category else None,
    }
    payload = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _keyword_rows(
    project_id: int, run_id: int, results: list[McpCallResult]
) -> list[ResearchKeyword]:
    rows: list[ResearchKeyword] = []
    seen: set[str] = set()
    for result in results:
        for index, record in enumerate(result.records):
            keyword = record.get("keyword")
            if not isinstance(keyword, str) or not keyword.strip():
                continue
            normalized = normalize_keyword(keyword)
            if normalized in seen:
                continue
            seen.add(normalized)
            lineage = result.field_lineage[index] if index < len(result.field_lineage) else {}
            metrics = {
                key: value for key, value in record.items()
                if key not in _MODEL_FIELDS and key != "keyword"
            }
            metrics.update({
                "source_id": result.source_id,
                "source_name": result.source_name,
                "collected_at": result.collected_at.isoformat(),
            })
            rows.append(
                ResearchKeyword(
                    project_id=project_id,
                    run_id=run_id,
                    keyword=keyword,
                    normalized_keyword=normalized,
                    metrics_json=metrics,
                    field_lineage_json=lineage,
                    **{name: record.get(name) for name in _MODEL_FIELDS},
                )
            )
    return rows


def _build_snapshot(
    project_id: int,
    run_id: int,
    arguments: dict[str, Any],
    result: McpCallResult,
) -> SourceSnapshot:
    response = result.raw_data
    if response is None:
        response = {"status": result.status, "warnings": result.warnings}
    return SourceSnapshot(
        project_id=project_id,
        research_run_id=run_id,
        source_id=result.source_id,
        capability=result.capability.value,
        tool_name=result.tool_name,
        request_json_redacted=_redact(arguments),
        response_json_redacted=_redact(response),
        truncated=False,
        collected_at=result.collected_at,
    )


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "[已脱敏]" if any(part in str(key).casefold() for part in _SENSITIVE_PARTS) else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
