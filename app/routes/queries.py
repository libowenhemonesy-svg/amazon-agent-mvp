"""查询路由"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_session
from app.db.repository import get_daily_report, list_alerts, list_metrics, update_alert_status

router = APIRouter(tags=["查询"])


@router.get("/metrics/daily")
def get_metrics_daily(
    date: date,
    session: Session = Depends(get_session),
) -> list[dict]:
    return list_metrics(session, date)


@router.get("/alerts")
def get_alerts(
    session: Session = Depends(get_session),
    date: date | None = None,
) -> list[dict]:
    return list_alerts(session, date)


@router.patch("/alerts/{alert_id}")
def patch_alert(
    alert_id: int,
    payload: dict,
    session: Session = Depends(get_session),
) -> dict:
    alert = update_alert_status(session, alert_id, payload.get("status", ""))
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"id": alert.id, "status": alert.status}


@router.get("/reports/daily")
def get_report_daily(
    date: date,
    session: Session = Depends(get_session),
) -> dict:
    report = get_daily_report(session, date)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
