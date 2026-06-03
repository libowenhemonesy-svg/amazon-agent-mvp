from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.agents.chat_graph import ChatGraph
from app.agents.llm import build_llm_client
from app.agents.tools import ChatTools
from app.automation.handlers import handle_daily_analysis, handle_data_sync, handle_competitor_monitor
from app.automation.scheduler import AutomationScheduler, AutomationTask, TaskType, TaskStatus, init_default_tasks, scheduler
from app.db.models import Base
from app.db.session import build_session_factory, ensure_sqlite_dev_schema
from app.deps import init_session_factory
from app.env import load_env_file
from app.routes.analysis import init_product_research_ai, router as analysis_router
from app.routes.automation import router as automation_router
from app.routes.chat import init_chat_graph, router as chat_router
from app.routes.chrome import router as chrome_router
from app.routes.demo import router as demo_router
from app.routes.imports import router as imports_router
from app.routes.jobs import router as jobs_router
from app.routes.queries import router as queries_router
from app.routes.settings import router as settings_router

load_env_file(Path.cwd() / ".env")


def create_app(
    *,
    database_url: str = "sqlite+pysqlite:///./amazon_agent.db",
    feishu_enabled: bool = True,
    product_research_ai_enabled: bool = True,
) -> FastAPI:
    session_factory = build_session_factory(database_url)
    Base.metadata.create_all(session_factory.kw["bind"])
    ensure_sqlite_dev_schema(session_factory.kw["bind"])

    # 初始化全局会话工厂
    init_session_factory(session_factory)

    app = FastAPI(title="Amazon Agent MVP", version="0.1.0")

    # 添加 CORS 支持
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # 初始化产品研究 AI 配置
    init_product_research_ai(product_research_ai_enabled)

    # 注册路由
    app.include_router(imports_router)
    app.include_router(jobs_router)
    app.include_router(queries_router)
    app.include_router(chat_router)
    app.include_router(analysis_router)
    app.include_router(automation_router)
    app.include_router(chrome_router)
    app.include_router(settings_router)
    app.include_router(demo_router)

    @app.get("/")
    def dashboard():
        from fastapi.responses import FileResponse
        index_path = static_dir / "index.html"
        if not index_path.exists():
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Dashboard not found")
        return FileResponse(index_path)

    # 初始化聊天 Agent
    chat_tools = ChatTools(session_factory)
    llm_client = build_llm_client(os.environ)
    chat_graph = ChatGraph(llm_client, chat_tools)
    init_chat_graph(chat_graph)

    # 注册自动化任务处理器
    scheduler.register_handler(TaskType.DAILY_ANALYSIS, handle_daily_analysis)
    scheduler.register_handler(TaskType.DATA_SYNC, handle_data_sync)
    scheduler.register_handler(TaskType.COMPETITOR_MONITOR, handle_competitor_monitor)

    # 初始化默认任务
    init_default_tasks()

    @app.on_event("startup")
    async def startup_scheduler():
        """启动时启动调度器"""
        await scheduler.start()

    @app.on_event("shutdown")
    async def shutdown_scheduler():
        """关闭时停止调度器"""
        await scheduler.stop()

    return app


app = create_app(database_url=os.getenv("DATABASE_URL", "sqlite+pysqlite:///./amazon_agent.db"))
