"""自动化任务路由"""
from __future__ import annotations

import asyncio
from datetime import time as dt_time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.automation.scheduler import scheduler

router = APIRouter(prefix="/api/automation", tags=["自动化任务"])


class AutomationTaskUpdate(BaseModel):
    schedule_time: str | None = None
    enabled: bool | None = None
    config: dict | None = None


@router.get("/tasks")
def get_automation_tasks() -> list[dict]:
    """获取所有自动化任务"""
    return scheduler.get_all_tasks()


@router.get("/tasks/{task_id}")
def get_automation_task(task_id: str) -> dict:
    """获取单个自动化任务"""
    task = scheduler.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task.to_dict()


@router.post("/tasks/{task_id}/enable")
def enable_automation_task(task_id: str) -> dict:
    """启用任务"""
    task = scheduler.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    scheduler.enable_task(task_id)
    return {"success": True, "message": f"任务 {task.name} 已启用"}


@router.post("/tasks/{task_id}/disable")
def disable_automation_task(task_id: str) -> dict:
    """禁用任务"""
    task = scheduler.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    scheduler.disable_task(task_id)
    return {"success": True, "message": f"任务 {task.name} 已禁用"}


@router.post("/tasks/{task_id}/run")
async def run_automation_task(task_id: str) -> dict:
    """立即执行任务"""
    task = scheduler.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    handler = scheduler.handlers.get(task.task_type)
    if not handler:
        raise HTTPException(status_code=400, detail="未找到任务处理器")

    try:
        if asyncio.iscoroutinefunction(handler):
            result = await handler(task.config)
        else:
            result = handler(task.config)

        task.last_result = result
        task.run_count += 1
        return {"success": True, "result": result}
    except Exception as e:
        task.error_count += 1
        return {"success": False, "error": str(e)}


@router.patch("/tasks/{task_id}")
def update_automation_task(task_id: str, payload: AutomationTaskUpdate) -> dict:
    """更新任务配置"""
    task = scheduler.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if payload.schedule_time is not None:
        hour, minute = map(int, payload.schedule_time.split(":"))
        task.schedule_time = dt_time(hour, minute)
        scheduler._update_next_run(task)

    if payload.enabled is not None:
        if payload.enabled:
            scheduler.enable_task(task_id)
        else:
            scheduler.disable_task(task_id)

    if payload.config is not None:
        task.config = payload.config

    return {"success": True, "task": task.to_dict()}
