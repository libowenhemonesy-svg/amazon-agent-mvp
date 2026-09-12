from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.agents.agent_status_agent import AgentStatusAgent
from app.agents.chat_graph import ChatGraph
from app.agents.llm import build_llm_client
from app.agents.mcp_tools import load_sellersprite_mcp_tools
from app.agents.orchestrator_graph import OrchestratorGraph
from app.agents.product_image_agent import BailianImageClient, ProductImageAgent
from app.agents.product_listing_agent import ProductListingAgent
from app.agents.tools import ChatTools
from app.automation.handlers import handle_daily_analysis, handle_data_sync, handle_competitor_monitor
from app.automation.scheduler import AutomationScheduler, AutomationTask, TaskType, TaskStatus, init_default_tasks, scheduler
from app.db.models import Base
from app.db.session import build_session_factory, ensure_sqlite_dev_schema
from app.deps import init_session_factory
from app.env import load_env_file
from app.memory.factory import build_memory_service
from app.routes.analysis import (
    init_listing_llm_client,
    router as analysis_router,
)
from app.auth.router import router as auth_router
from app.routes.automation import router as automation_router
from app.routes.chat import init_chat_graph, init_chat_memory_service, router as chat_router
from app.routes.chrome import router as chrome_router
from app.routes.demo import init_demo_config, router as demo_router
from app.routes.dianxiaomi import init_dianxiaomi_agent, router as dianxiaomi_router
from app.routes.jobs import init_jobs_config, router as jobs_router
from app.routes.image_studio import router as image_studio_router
from app.routes.operations import router as operations_router
from app.routes.queries import router as queries_router
from app.routes.rag import init_rag_engine, router as rag_router
from app.routes.settings import router as settings_router
from app.routes.selection import init_selection_llm_client, router as selection_router
from app.rag.config import EMBEDDING_MODEL, UPLOAD_DIR, VECTOR_DB_DIR
from app.rag.embeddings import EmbeddingService
from app.rag.rag_engine import RAGEngine
from app.rag.vector_store import VectorStore

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_env_file(PROJECT_ROOT / ".env", override=True)
if Path.cwd().resolve() != PROJECT_ROOT:
    load_env_file(Path.cwd() / ".env", override=True)


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

    app = FastAPI(title="全能运营智能体", version="0.1.0")

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
    image_assets_dir = Path(
        os.getenv("IMAGE_STUDIO_OUTPUT_DIR")
        or static_dir / "generated" / "image-studio"
    )
    image_assets_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/image-assets", StaticFiles(directory=image_assets_dir), name="image-assets")

    init_jobs_config(feishu_enabled=feishu_enabled)
    init_demo_config(feishu_enabled=feishu_enabled)

    # 注册路由
    app.include_router(auth_router)
    app.include_router(jobs_router)
    app.include_router(queries_router)
    app.include_router(chat_router)
    app.include_router(chrome_router)
    app.include_router(analysis_router)
    app.include_router(automation_router)
    app.include_router(settings_router)
    app.include_router(selection_router)
    app.include_router(demo_router)
    app.include_router(dianxiaomi_router)
    app.include_router(image_studio_router)
    app.include_router(operations_router)

    @app.get("/")
    def dashboard():
        from fastapi.responses import FileResponse
        index_path = static_dir / "index.html"
        if not index_path.exists():
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Dashboard not found")
        return FileResponse(index_path)

    @app.get("/rag")
    def rag_page():
        from fastapi.responses import FileResponse
        rag_path = static_dir / "rag.html"
        if not rag_path.exists():
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="RAG page not found")
        return FileResponse(rag_path)

    @app.get("/login")
    def login_page():
        from fastapi.responses import FileResponse
        login_path = static_dir / "login.html"
        if not login_path.exists():
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Login page not found")
        return FileResponse(login_path)

    # 初始化聊天 Agent
    chat_tools = ChatTools(session_factory)
    llm_client = build_llm_client(os.environ)
    init_listing_llm_client(llm_client)
    init_selection_llm_client(llm_client)
    memory_service = build_memory_service(session_factory=session_factory, env=os.environ)
    init_chat_memory_service(memory_service)
    init_dianxiaomi_agent(llm_client=llm_client)
    # 初始化 RAG 模块
    Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(VECTOR_DB_DIR).mkdir(parents=True, exist_ok=True)
    try:
        embedding_service = EmbeddingService(model_name=EMBEDDING_MODEL)
    except RuntimeError:
        init_rag_engine(None)
    else:
        vector_store = VectorStore(persist_dir=VECTOR_DB_DIR, embedding_service=embedding_service)
        rag_engine = RAGEngine(
            vector_store=vector_store,
            embedding_service=embedding_service,
            llm_client=llm_client,
        )
        init_rag_engine(rag_engine)
    app.include_router(rag_router)

    chat_graph = ChatGraph(
        llm_client,
        chat_tools,
        mcp_tools_loader=lambda: load_sellersprite_mcp_tools(os.environ),
        memory_service=memory_service,
    )
    product_image_agent = ProductImageAgent(
        output_dir=static_dir / "generated",
        image_client=BailianImageClient.from_env(os.environ),
    )
    product_listing_agent = ProductListingAgent(llm_client=llm_client)
    agent_status_agent = AgentStatusAgent(llm_client=llm_client)
    orchestrator = OrchestratorGraph(
        chat_graph=chat_graph,
        executors={
            "agent_status": agent_status_agent.run,
            "product_listing": lambda state: product_listing_agent.run(
                state,
                research_context=state.get("research_context", {}),
            ),
            "product_image": lambda state: product_image_agent.run(
                state,
                research_context=state.get("research_context", {}),
            ),
        },
    )
    init_chat_graph(orchestrator)

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
