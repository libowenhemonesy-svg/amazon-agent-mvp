from __future__ import annotations

import json
import re
from typing import Any


def parse_agent_response(
    raw: Any,
    *,
    fallback_summary: str,
    severity: str,
    fallback_root_causes: list[str] | None = None,
    fallback_diagnostic_checks: list[str] | None = None,
    fallback_recommended_actions: list[str] | None = None,
) -> dict[str, Any]:
    payload = _load_payload(raw)
    if not isinstance(payload, dict):
        return _fallback(
            fallback_summary,
            severity,
            fallback_root_causes=fallback_root_causes,
            fallback_diagnostic_checks=fallback_diagnostic_checks,
            fallback_recommended_actions=fallback_recommended_actions,
        )

    root_causes = _list(payload.get("root_causes") or payload.get("possible_causes"), limit=3)
    diagnostic_checks = _list(payload.get("diagnostic_checks"), limit=4)
    recommended_actions = _list(payload.get("recommended_actions"), limit=4)
    summary = _short_text(payload.get("summary"), limit=60)
    if not summary:
        return _fallback(
            fallback_summary,
            severity,
            fallback_root_causes=fallback_root_causes,
            fallback_diagnostic_checks=fallback_diagnostic_checks,
            fallback_recommended_actions=fallback_recommended_actions,
        )

    if not root_causes:
        root_causes = fallback_root_causes or _fallback_causes()
    if not diagnostic_checks:
        diagnostic_checks = fallback_diagnostic_checks or ["核对规则命中指标", "检查近期运营动作"]
    if not recommended_actions:
        recommended_actions = fallback_recommended_actions or ["安排负责人复核并记录处理动作"]

    return {
        "summary": summary,
        "root_causes": root_causes,
        "possible_causes": root_causes,
        "diagnostic_checks": diagnostic_checks,
        "recommended_actions": recommended_actions,
        "priority": _priority(payload.get("priority"), severity),
        "immediate_action_required": _bool(
            payload.get("immediate_action_required"),
            default=severity == "high",
        ),
    }


def _load_payload(raw: Any) -> Any:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _fallback(
    fallback_summary: str,
    severity: str,
    *,
    fallback_root_causes: list[str] | None = None,
    fallback_diagnostic_checks: list[str] | None = None,
    fallback_recommended_actions: list[str] | None = None,
) -> dict[str, Any]:
    root_causes = fallback_root_causes or _fallback_causes()
    return {
        "summary": _short_text(fallback_summary, limit=60) or "规则命中异常，需要运营人员复核",
        "root_causes": root_causes,
        "possible_causes": root_causes,
        "diagnostic_checks": fallback_diagnostic_checks or ["核对规则命中指标", "检查近期运营动作"],
        "recommended_actions": fallback_recommended_actions or ["安排负责人复核并记录处理动作"],
        "priority": _priority(None, severity),
        "immediate_action_required": severity == "high",
    }


def _fallback_causes() -> list[str]:
    return ["规则命中异常", "近期指标偏离阈值"]


def _list(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_short_text(item, limit=60) for item in value[:limit] if _short_text(item, limit=60)]


def _short_text(value: Any, *, limit: int) -> str:
    if value is None:
        return ""
    text = str(value).strip().replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text[:limit]


def _priority(value: Any, severity: str) -> int:
    try:
        priority = int(value)
    except (TypeError, ValueError):
        priority = {"high": 1, "medium": 2, "low": 3}.get(severity, 2)
    return priority if priority in {1, 2, 3} else {"high": 1, "medium": 2, "low": 3}.get(severity, 2)


def _bool(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes", "是"}
    return default
