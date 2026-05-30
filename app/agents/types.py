from __future__ import annotations

from typing import Literal, TypedDict

from pydantic import BaseModel


class OpsGraphState(TypedDict):
    run_date: str
    alert_id: int
    sku: str
    alert_type: str
    severity: str
    metrics: dict
    history: list[dict]
    rule_context: dict
    agent_result: dict
    feishu_sync_status: str
    errors: list[str]


class AgentResult(BaseModel):
    agent_name: str
    abnormal: bool
    summary: str
    root_causes: list[str]
    possible_causes: list[str]
    diagnostic_checks: list[str]
    recommended_actions: list[str]
    priority: int
    immediate_action_required: bool
    severity: Literal["low", "medium", "high"]
