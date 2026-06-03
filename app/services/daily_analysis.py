"""每日分析服务"""
from __future__ import annotations

import os
from datetime import date

from sqlalchemy.orm import Session

from app.agents.graph import build_ops_graph
from app.agents.llm import build_llm_client
from app.db.models import AdsDaily, InventoryDaily, ProfitDaily, ReturnReviewDaily, SalesDaily
from app.db.repository import (
    get_daily_report,
    list_alerts,
    list_daily_rows,
    list_skus,
    replace_metrics,
    save_daily_report,
    update_alert_agent_result,
    upsert_alerts,
)
from app.integrations.feishu.client import FeishuClient
from app.integrations.feishu.sync import sync_daily_outputs
from app.metrics.calculator import calculate_daily_metrics
from app.rules.engine import evaluate_alert_rules


def _noop_feishu_sync(state: dict) -> str:
    return "skipped"


def _build_feishu_client() -> FeishuClient | None:
    app_token = os.getenv("FEISHU_APP_TOKEN")
    access_token = os.getenv("FEISHU_TENANT_ACCESS_TOKEN")
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    table_ids = {
        "sku": os.getenv("FEISHU_TABLE_SKU", ""),
        "metrics": os.getenv("FEISHU_TABLE_METRICS", ""),
        "alerts": os.getenv("FEISHU_TABLE_ALERTS", ""),
        "reports": os.getenv("FEISHU_TABLE_REPORTS", ""),
    }
    if not app_token or any(not table_id for table_id in table_ids.values()):
        return None
    if not access_token and app_id and app_secret:
        access_token = FeishuClient.get_tenant_access_token(app_id=app_id, app_secret=app_secret)
    if not access_token:
        return None
    return FeishuClient(app_token=app_token, access_token=access_token, table_ids=table_ids)


def _sync_daily_to_feishu(
    *,
    enabled: bool,
    sku_rows: list[dict],
    metrics: list[dict],
    alerts: list[dict],
    report: dict,
) -> dict:
    if not enabled:
        return {"status": "disabled"}
    client = _build_feishu_client()
    if not client:
        return {"status": "skipped", "reason": "missing_feishu_env"}
    try:
        counts = sync_daily_outputs(
            client=client,
            sku_rows=sku_rows,
            metrics=metrics,
            alerts=alerts,
            report=report,
        )
        return {"status": "synced", "counts": counts}
    except Exception as exc:  # pragma: no cover - external API boundary
        return {"status": "failed", "error": str(exc)}


def run_daily_analysis(
    *,
    run_date: date,
    session: Session,
    feishu_enabled: bool,
) -> dict:
    """执行每日分析流程"""
    sku_rows = list_skus(session)
    metrics = calculate_daily_metrics(
        run_date,
        sku_rows,
        list_daily_rows(session, SalesDaily, run_date),
        list_daily_rows(session, AdsDaily, run_date),
        list_daily_rows(session, InventoryDaily, run_date),
        list_daily_rows(session, ProfitDaily, run_date),
        list_daily_rows(session, ReturnReviewDaily, run_date),
    )
    replace_metrics(session, run_date, metrics)
    alerts = upsert_alerts(session, evaluate_alert_rules(metrics))
    metric_by_sku = {row["sku"]: row for row in metrics}
    graph = build_ops_graph(
        llm_client=build_llm_client(os.environ),
        feishu_sync=_noop_feishu_sync,
    )
    for alert in alerts:
        state = graph.invoke(
            {
                "run_date": run_date.isoformat(),
                "alert_id": alert.id,
                "sku": alert.sku,
                "alert_type": alert.alert_type,
                "severity": alert.severity,
                "metrics": metric_by_sku.get(alert.sku, {}),
                "history": [],
                "rule_context": alert.rule_context or {},
                "agent_result": {},
                "feishu_sync_status": "",
                "errors": [],
            }
        )
        update_alert_agent_result(
            session,
            alert.id,
            state["agent_result"],
            state["feishu_sync_status"],
        )
    alert_dicts = list_alerts(session, run_date)
    report = save_daily_report(session, run_date, alert_dicts)
    feishu_sync_status = _sync_daily_to_feishu(
        enabled=feishu_enabled,
        sku_rows=sku_rows,
        metrics=metrics,
        alerts=alert_dicts,
        report=get_daily_report(session, run_date) or {},
    )
    return {
        "date": run_date.isoformat(),
        "metrics_created": len(metrics),
        "alerts_created": len(alerts),
        "feishu_sync": feishu_sync_status,
    }
