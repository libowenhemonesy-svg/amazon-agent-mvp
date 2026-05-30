from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Type

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import (
    AdsDaily,
    AlertTask,
    DailyReport,
    InventoryDaily,
    ProfitDaily,
    ReturnReviewDaily,
    SalesDaily,
    SkuMaster,
    SkuMetricsDaily,
)
from app.reports.director import build_director_report


def upsert_sku_rows(session: Session, rows: list[dict[str, Any]]) -> int:
    for row in rows:
        sku = str(row["sku"])
        existing = session.get(SkuMaster, sku)
        values = {
            "sku": sku,
            "asin": row.get("asin"),
            "platform_link": row.get("platform_link"),
            "store": row.get("store"),
            "marketplace": row.get("marketplace"),
            "product_category": row.get("product_category"),
            "owner": row.get("owner"),
            "responsible_agent": row.get("responsible_agent"),
            "lifecycle": row.get("lifecycle") or "stable",
            "target_acos": _float(row.get("target_acos"), 0.3),
            "target_gross_margin": _float(row.get("target_gross_margin"), 0.4),
            "safety_stock_days": int(_float(row.get("safety_stock_days"), 30)),
            "replenishment_days": int(_float(row.get("replenishment_days"), 20)),
            "enabled": _bool(row.get("enabled", True)),
        }
        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
        else:
            session.add(SkuMaster(**values))
    session.commit()
    return len(rows)


def upsert_daily_rows(session: Session, model: Type, rows: list[dict[str, Any]]) -> int:
    for row in rows:
        sku = str(row["sku"])
        row_date = _date(row["date"])
        session.execute(delete(model).where(model.sku == sku, model.date == row_date))
        session.add(model(**{**row, "sku": sku, "date": row_date}))
    session.commit()
    return len(rows)


def list_skus(session: Session) -> list[dict[str, Any]]:
    return [
        {
            "sku": row.sku,
            "asin": row.asin,
            "platform_link": row.platform_link,
            "store": row.store,
            "marketplace": row.marketplace,
            "product_category": row.product_category,
            "owner": row.owner,
            "responsible_agent": row.responsible_agent,
            "target_acos": row.target_acos,
            "target_gross_margin": row.target_gross_margin,
            "safety_stock_days": row.safety_stock_days,
            "replenishment_days": row.replenishment_days,
            "lifecycle": row.lifecycle,
            "enabled": row.enabled,
        }
        for row in session.scalars(select(SkuMaster).where(SkuMaster.enabled.is_(True))).all()
    ]


def list_daily_rows(session: Session, model: Type, run_date: date, lookback_days: int = 30) -> list[dict[str, Any]]:
    start = run_date - timedelta(days=lookback_days - 1)
    rows = session.scalars(select(model).where(model.date >= start, model.date <= run_date)).all()
    return [_model_dict(row) for row in rows]


def replace_metrics(session: Session, run_date: date, metrics: list[dict[str, Any]]) -> None:
    session.execute(delete(SkuMetricsDaily).where(SkuMetricsDaily.date == run_date))
    for row in metrics:
        session.add(SkuMetricsDaily(sku=row["sku"], date=run_date, metrics=_jsonable(row)))
    session.commit()


def list_metrics(session: Session, run_date: date) -> list[dict[str, Any]]:
    rows = session.scalars(select(SkuMetricsDaily).where(SkuMetricsDaily.date == run_date)).all()
    return [row.metrics for row in rows]


def upsert_alerts(session: Session, alerts: list[dict[str, Any]]) -> list[AlertTask]:
    saved: list[AlertTask] = []
    for alert in alerts:
        alert_date = _date(alert["date"])
        existing = session.scalar(
            select(AlertTask).where(
                AlertTask.date == alert_date,
                AlertTask.sku == alert["sku"],
                AlertTask.alert_type == alert["alert_type"],
            )
        )
        if existing:
            saved.append(existing)
            continue
        task = AlertTask(
            date=alert_date,
            sku=alert["sku"],
            alert_type=alert["alert_type"],
            severity=alert["severity"],
            reason=alert["reason"],
            rule_context=alert.get("rule_context", {}),
        )
        session.add(task)
        session.flush()
        saved.append(task)
    session.commit()
    return saved


def update_alert_agent_result(
    session: Session,
    alert_id: int,
    agent_result: dict,
    feishu_sync_status: str,
) -> None:
    alert = session.get(AlertTask, alert_id)
    if not alert:
        return
    alert.agent_result = agent_result
    alert.feishu_sync_status = feishu_sync_status
    session.commit()


def update_alert_status(session: Session, alert_id: int, status: str) -> AlertTask | None:
    alert = session.get(AlertTask, alert_id)
    if not alert:
        return None
    alert.status = status
    session.commit()
    return alert


def list_alerts(session: Session, run_date: date | None = None) -> list[dict[str, Any]]:
    statement = select(AlertTask)
    if run_date:
        statement = statement.where(AlertTask.date == run_date)
    rows = session.scalars(statement.order_by(AlertTask.severity.desc(), AlertTask.id)).all()
    return [_alert_dict(row) for row in rows]


def save_daily_report(session: Session, run_date: date, alerts: list[dict[str, Any]]) -> DailyReport:
    report_data = build_director_report(run_date.isoformat(), alerts)
    existing = session.scalar(select(DailyReport).where(DailyReport.date == run_date))
    values = {
        "summary": report_data["summary"],
        "risk_count": report_data["risk_count"],
        "pending_count": report_data["pending_count"],
        "report_data": report_data,
    }
    if existing:
        for key, value in values.items():
            setattr(existing, key, value)
        report = existing
    else:
        report = DailyReport(date=run_date, **values)
        session.add(report)
    session.commit()
    return report


def get_daily_report(session: Session, run_date: date) -> dict[str, Any] | None:
    report = session.scalar(select(DailyReport).where(DailyReport.date == run_date))
    if not report:
        return None
    return {
        "date": report.date.isoformat(),
        "summary": report.summary,
        "risk_count": report.risk_count,
        "pending_count": report.pending_count,
        "report_data": report.report_data,
    }


def delete_daily_run_outputs(session: Session, run_date: date) -> dict[str, int]:
    deleted_alerts = session.execute(delete(AlertTask).where(AlertTask.date == run_date)).rowcount or 0
    deleted_reports = session.execute(delete(DailyReport).where(DailyReport.date == run_date)).rowcount or 0
    deleted_metrics = session.execute(delete(SkuMetricsDaily).where(SkuMetricsDaily.date == run_date)).rowcount or 0
    session.commit()
    return {
        "deleted_alerts": deleted_alerts,
        "deleted_reports": deleted_reports,
        "deleted_metrics": deleted_metrics,
    }


def _model_dict(row: Any) -> dict[str, Any]:
    return {
        column.name: getattr(row, column.name)
        for column in row.__table__.columns
        if column.name not in {"id", "created_at"}
    }


def _alert_dict(row: AlertTask) -> dict[str, Any]:
    return {
        "id": row.id,
        "date": row.date.isoformat(),
        "sku": row.sku,
        "alert_type": row.alert_type,
        "severity": row.severity,
        "reason": row.reason,
        "rule_context": row.rule_context or {},
        "status": row.status,
        "agent_result": row.agent_result or {},
        "feishu_sync_status": row.feishu_sync_status,
    }


def _jsonable(row: dict[str, Any]) -> dict[str, Any]:
    return {key: (value.isoformat() if hasattr(value, "isoformat") else value) for key, value in row.items()}


def _date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _float(value: Any, default: float) -> float:
    if value is None or value == "":
        return default
    return float(value)


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() not in {"false", "0", "no", "否"}
