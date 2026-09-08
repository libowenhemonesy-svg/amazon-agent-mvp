from __future__ import annotations

import json
from decimal import Decimal

from app.auth.dependencies import get_current_user
from app.auth.schemas import UserInfo
from app.db.models import PricingSnapshot, ProductDirection
from app.routes.selection import get_report_llm_client
from app.selection.report_service import ReportService


class FakeLLM:
    def __init__(self, response: str | None = None, error: Exception | None = None):
        self.response = response or json.dumps({
            "summary": "该方向可进入验证阶段。",
            "findings": ["需求与利润指标达到规则阈值"],
            "risks": ["仍需持续核对竞品变化"],
            "actions": ["先进行小批量测试"],
        }, ensure_ascii=False)
        self.error = error
        self.prompts = []

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.prompts.append((system_prompt, user_prompt))
        if self.error:
            raise self.error
        return self.response


def _complete_project(session):
    from app.selection.repository import SelectionRepository

    project = SelectionRepository(session).create_project("alice", "便携风扇", "US", "USD")
    session.add(ProductDirection(
        project_id=project.id,
        name="portable fan",
        keyword_cluster_json={"all": ["portable fan"]},
        market_metrics_json={
            "rule_metrics": {
                "demand": 85,
                "competition": 65,
                "profit": 88,
                "trend": 80,
                "differentiation": 67,
                "quality": 80,
                "coverage": 1.0,
            },
            "warnings": [],
        },
        competitors_json={"search": []},
        field_lineage_json={"records": []},
        data_completeness=1.0,
    ))
    session.add(PricingSnapshot(
        project_id=project.id,
        product_price=Decimal("30"),
        domestic_shipping=Decimal("0"),
        source_currency="USD",
        actual_weight_kg=Decimal("1"),
        length_cm=Decimal("0"),
        width_cm=Decimal("0"),
        height_cm=Decimal("0"),
        commission_rate=Decimal("0.15"),
        target_net_margin=Decimal("0.40"),
        freight_template_snapshot_json={"id": 1, "currency": "USD"},
        exchange_rate_snapshot_json={"rate": "1", "source_name": "same_currency"},
        volumetric_weight_kg=Decimal("0"),
        billable_weight_kg=Decimal("1"),
        international_shipping=Decimal("15"),
        target_price=Decimal("100"),
        commission_amount=Decimal("15"),
        net_profit_amount=Decimal("40"),
    ))
    session.commit()
    return project


def test_report_uses_rule_score_and_real_llm_text(session):
    project = _complete_project(session)
    fake_llm = FakeLLM()

    report = ReportService(session=session, llm_client=fake_llm).generate(project.id, "alice")

    assert report.score_total == 78
    assert report.decision == "recommended"
    assert report.llm_status == "succeeded"
    assert report.llm_report["summary"] == "该方向可进入验证阶段。"
    assert "78" in fake_llm.prompts[0][1]


def test_missing_llm_does_not_create_fallback_report(session):
    project = _complete_project(session)
    report = ReportService(session=session, llm_client=None).generate(project.id, "alice")
    assert report.score_total == 78
    assert report.llm_status == "unavailable"
    assert report.llm_report is None


def test_provider_error_and_invalid_json_do_not_create_fallback(session):
    project = _complete_project(session)
    failed = ReportService(
        session=session,
        llm_client=FakeLLM(error=RuntimeError("Authorization Bearer secret-token")),
    ).generate(project.id, "alice")
    invalid = ReportService(
        session=session,
        llm_client=FakeLLM(response='{"summary":"ok","findings":[]}'),
    ).generate(project.id, "alice")

    assert failed.llm_status == "failed"
    assert failed.llm_report is None
    assert "secret-token" not in str(failed.risks_json)
    assert invalid.llm_status == "failed"
    assert invalid.llm_report is None


def test_missing_rule_metrics_blocks_llm_and_marks_needs_data(session):
    project = _complete_project(session)
    direction = session.query(ProductDirection).filter_by(project_id=project.id).one()
    direction.market_metrics_json = {"warnings": ["缺少可评分指标"]}
    session.commit()
    fake_llm = FakeLLM()

    report = ReportService(session=session, llm_client=fake_llm).generate(project.id, "alice")

    assert report.score_total is None
    assert report.decision == "needs_data"
    assert report.llm_status == "unavailable"
    assert report.llm_report is None
    assert fake_llm.prompts == []


def test_report_is_scoped_to_owned_project(session):
    project = _complete_project(session)
    try:
        ReportService(session=session, llm_client=None).generate(project.id, "bob")
    except LookupError as exc:
        assert str(exc) == "选品项目不存在"
    else:
        raise AssertionError("跨用户不应生成报告")


def test_report_api_uses_injected_llm_and_is_user_scoped(
    app, client_as_user, session_factory
):
    with session_factory() as db:
        project = _complete_project(db)
        project_id = project.id
    fake_llm = FakeLLM()
    app.dependency_overrides[get_report_llm_client] = lambda: fake_llm

    response = client_as_user.post(f"/api/selection/projects/{project_id}/report")

    assert response.status_code == 200
    assert response.json()["score_total"] == 78
    assert response.json()["llm_status"] == "succeeded"
    assert client_as_user.get(
        f"/api/selection/projects/{project_id}/report"
    ).status_code == 200

    app.dependency_overrides[get_current_user] = lambda: UserInfo(
        username="bob", display_name="Bob", role="user", is_active=True
    )
    assert client_as_user.get(
        f"/api/selection/projects/{project_id}/report"
    ).status_code == 404
