"""自动化任务调度器"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    DISABLED = "disabled"


class TaskType(str, Enum):
    DAILY_ANALYSIS = "daily_analysis"
    DATA_SYNC = "data_sync"
    COMPETITOR_MONITOR = "competitor_monitor"


class AutomationTask:
    """自动化任务"""

    def __init__(
        self,
        task_id: str,
        name: str,
        task_type: TaskType,
        schedule_time: time,
        enabled: bool = True,
        config: dict = None,
    ):
        self.task_id = task_id
        self.name = name
        self.task_type = task_type
        self.schedule_time = schedule_time
        self.enabled = enabled
        self.config = config or {}
        self.status = TaskStatus.PENDING
        self.last_run = None
        self.next_run = None
        self.last_result = None
        self.run_count = 0
        self.error_count = 0

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "task_type": self.task_type.value,
            "schedule_time": self.schedule_time.strftime("%H:%M"),
            "enabled": self.enabled,
            "config": self.config,
            "status": self.status.value,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "last_result": self.last_result,
            "run_count": self.run_count,
            "error_count": self.error_count,
        }


class AutomationScheduler:
    """自动化任务调度器"""

    def __init__(self):
        self.tasks: dict[str, AutomationTask] = {}
        self.handlers: dict[TaskType, Callable] = {}
        self._running = False
        self._task = None

    def register_handler(self, task_type: TaskType, handler: Callable):
        """注册任务处理器"""
        self.handlers[task_type] = handler

    def add_task(self, task: AutomationTask):
        """添加任务"""
        self.tasks[task.task_id] = task
        self._update_next_run(task)
        logger.info(f"添加自动化任务: {task.name} ({task.task_id})")

    def remove_task(self, task_id: str):
        """移除任务"""
        if task_id in self.tasks:
            del self.tasks[task_id]
            logger.info(f"移除自动化任务: {task_id}")

    def enable_task(self, task_id: str):
        """启用任务"""
        if task_id in self.tasks:
            self.tasks[task_id].enabled = True
            self._update_next_run(self.tasks[task_id])

    def disable_task(self, task_id: str):
        """禁用任务"""
        if task_id in self.tasks:
            self.tasks[task_id].enabled = False
            self.tasks[task_id].status = TaskStatus.DISABLED

    def get_task(self, task_id: str) -> AutomationTask | None:
        """获取任务"""
        return self.tasks.get(task_id)

    def get_all_tasks(self) -> list[dict]:
        """获取所有任务"""
        return [task.to_dict() for task in self.tasks.values()]

    def _update_next_run(self, task: AutomationTask):
        """更新下次运行时间"""
        now = datetime.now()
        scheduled = datetime.combine(now.date(), task.schedule_time)

        if scheduled <= now:
            # 如果今天的时间已过，设为明天
            from datetime import timedelta
            scheduled = scheduled + timedelta(days=1)

        task.next_run = scheduled

    async def start(self):
        """启动调度器"""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("自动化调度器已启动")

    async def stop(self):
        """停止调度器"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("自动化调度器已停止")

    async def _run_loop(self):
        """主循环"""
        while self._running:
            now = datetime.now()

            for task in self.tasks.values():
                if not task.enabled:
                    continue

                if task.next_run and now >= task.next_run:
                    await self._execute_task(task)

            # 每 30 秒检查一次
            await asyncio.sleep(30)

    async def _execute_task(self, task: AutomationTask):
        """执行任务"""
        logger.info(f"执行自动化任务: {task.name}")
        task.status = TaskStatus.RUNNING
        task.last_run = datetime.now()

        try:
            handler = self.handlers.get(task.task_type)
            if handler:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(task.config)
                else:
                    result = handler(task.config)

                task.status = TaskStatus.SUCCESS
                task.last_result = result
                task.run_count += 1
                logger.info(f"任务完成: {task.name}")
            else:
                task.status = TaskStatus.FAILED
                task.last_result = {"error": "未找到任务处理器"}
                task.error_count += 1
                logger.error(f"任务失败: {task.name} - 未找到处理器")
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.last_result = {"error": str(e)}
            task.error_count += 1
            logger.error(f"任务失败: {task.name} - {e}")

        # 更新下次运行时间
        self._update_next_run(task)


# 全局调度器实例
scheduler = AutomationScheduler()


def init_default_tasks():
    """初始化默认任务"""
    from datetime import time

    # 每日分析任务 - 每天早上 8:00
    scheduler.add_task(AutomationTask(
        task_id="daily_analysis",
        name="每日分析",
        task_type=TaskType.DAILY_ANALYSIS,
        schedule_time=time(8, 0),
        enabled=True,
        config={"run_date": "today"},
    ))

    # 数据同步任务 - 每天早上 7:00
    scheduler.add_task(AutomationTask(
        task_id="data_sync",
        name="数据同步",
        task_type=TaskType.DATA_SYNC,
        schedule_time=time(7, 0),
        enabled=True,
        config={"sources": ["eccang", "amazon"]},
    ))

    # 竞品监控任务 - 每天早上 9:00
    scheduler.add_task(AutomationTask(
        task_id="competitor_monitor",
        name="竞品监控",
        task_type=TaskType.COMPETITOR_MONITOR,
        schedule_time=time(9, 0),
        enabled=True,
        config={"marketplace": "US"},
    ))
