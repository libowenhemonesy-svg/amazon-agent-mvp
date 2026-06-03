"""定时任务路由"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_session
from app.db.repository import delete_daily_run_outputs
from app.services.daily_analysis import run_daily_analysis

router = APIRouter(prefix="/jobs", tags=["定时任务"])


@router.post("/daily-run")
def daily_run(
    run_date: date,
    session: Session = Depends(get_session),
) -> dict:
    """手动触发每日分析"""
    return run_daily_analysis(run_date=run_date, session=session, feishu_enabled=True)


@router.delete("/daily-run")
def reset_daily_run(
    run_date: date,
    session: Session = Depends(get_session),
) -> dict:
    """重置每日分析结果"""
    return {"date": run_date.isoformat(), **delete_daily_run_outputs(session, run_date)}
