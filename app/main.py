from __future__ import annotations

import os
from collections.abc import Generator
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from app.agents.graph import build_ops_graph
from app.agents.llm import build_llm_client
from app.agents.chat_graph import ChatGraph
from app.agents.tools import ChatTools
from app.analysis.battlefield import BattlefieldAnalyzer
from app.analysis.diagnosis import DiagnosisAnalyzer
from app.automation.scheduler import AutomationScheduler, AutomationTask, TaskType, TaskStatus, init_default_tasks, scheduler
from app.automation.handlers import handle_daily_analysis, handle_data_sync, handle_competitor_monitor
from app.integrations.eccang.client import EccangClient
from app.db.models import AdsDaily, Base, InventoryDaily, ProfitDaily, ReturnReviewDaily, SalesDaily
from app.db.repository import (
    get_daily_report,
    delete_daily_run_outputs,
    list_alerts,
    list_daily_rows,
    list_metrics,
    list_skus,
    replace_metrics,
    save_daily_report,
    update_alert_agent_result,
    update_alert_status,
    upsert_alerts,
    upsert_daily_rows,
    upsert_sku_rows,
)
from app.db.session import build_session_factory
from app.db.session import ensure_sqlite_dev_schema
from app.env import load_env_file
from app.importers.tabular import ImportValidationError, parse_tabular_upload
from app.integrations.feishu.client import FeishuClient
from app.integrations.feishu.sync import sync_daily_outputs
from app.metrics.calculator import calculate_daily_metrics
from app.rules.engine import evaluate_alert_rules


load_env_file(Path.cwd() / ".env")


class AlertUpdate(BaseModel):
    status: str


class ChatRequest(BaseModel):
    message: str
    conversation_id: str = "default"


def create_app(
    *,
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/amazon_agent",
    feishu_enabled: bool = True,
) -> FastAPI:
    session_factory = build_session_factory(database_url)
    Base.metadata.create_all(session_factory.kw["bind"])
    ensure_sqlite_dev_schema(session_factory.kw["bind"])

    app = FastAPI(title="Amazon Agent MVP", version="0.1.0")
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    def get_session() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    @app.get("/")
    def dashboard() -> FileResponse:
        index_path = static_dir / "index.html"
        if not index_path.exists():
            raise HTTPException(status_code=404, detail="Dashboard not found")
        return FileResponse(index_path)

    @app.post("/imports/sku")
    async def import_sku(
        file: Annotated[UploadFile, File()],
        session: Session = Depends(get_session),
    ) -> dict:
        rows = await _parse_upload(
            file,
            required_columns={"SKU": "sku"},
            optional_columns={
                "ASIN": "asin",
                "Platform Link": "platform_link",
                "Store": "store",
                "Marketplace": "marketplace",
                "Product Category": "product_category",
                "Owner": "owner",
                "Responsible Agent": "responsible_agent",
                "Lifecycle": "lifecycle",
                "Target ACOS": "target_acos",
                "Target Gross Margin": "target_gross_margin",
                "Safety Stock Days": "safety_stock_days",
                "Replenishment Days": "replenishment_days",
                "Enabled": "enabled",
            },
        )
        return {"imported": upsert_sku_rows(session, rows)}

    @app.post("/demo/load-sample")
    def load_sample_demo(session: Session = Depends(get_session)) -> dict:
        sample_dir = Path(__file__).resolve().parent.parent / "sample_data"
        imported = {
            "sku": upsert_sku_rows(
                session,
                _parse_sample_file(
                    sample_dir / "sku.csv",
                    required_columns={"SKU": "sku"},
                    optional_columns={
                        "ASIN": "asin",
                        "Platform Link": "platform_link",
                        "Store": "store",
                        "Marketplace": "marketplace",
                        "Product Category": "product_category",
                        "Owner": "owner",
                        "Responsible Agent": "responsible_agent",
                        "Lifecycle": "lifecycle",
                        "Target ACOS": "target_acos",
                        "Target Gross Margin": "target_gross_margin",
                        "Safety Stock Days": "safety_stock_days",
                        "Replenishment Days": "replenishment_days",
                        "Enabled": "enabled",
                    },
                ),
            ),
            "sales": upsert_daily_rows(
                session,
                SalesDaily,
                _parse_sample_file(
                    sample_dir / "sales.csv",
                    required_columns={"SKU": "sku", "Date": "date", "Units Sold": "units_sold"},
                    optional_columns={"Sales Amount": "sales_amount"},
                ),
            ),
            "ads": upsert_daily_rows(
                session,
                AdsDaily,
                _parse_sample_file(
                    sample_dir / "ads.csv",
                    required_columns={"SKU": "sku", "Date": "date"},
                    optional_columns={
                        "Impressions": "impressions",
                        "Clicks": "clicks",
                        "Spend": "spend",
                        "Ad Orders": "ad_orders",
                        "Ad Sales": "ad_sales",
                    },
                ),
            ),
            "inventory": upsert_daily_rows(
                session,
                InventoryDaily,
                _parse_sample_file(
                    sample_dir / "inventory.csv",
                    required_columns={"SKU": "sku", "Date": "date"},
                    optional_columns={
                        "Available Inventory": "available_inventory",
                        "Inbound Inventory": "inbound_inventory",
                        "Reserved Inventory": "reserved_inventory",
                    },
                ),
            ),
            "profit": upsert_daily_rows(
                session,
                ProfitDaily,
                _parse_sample_file(
                    sample_dir / "profit.csv",
                    required_columns={"SKU": "sku", "Date": "date"},
                    optional_columns={
                        "Product Cost": "product_cost",
                        "Platform Fees": "platform_fees",
                        "Logistics Fees": "logistics_fees",
                        "Ad Spend": "ad_spend",
                    },
                ),
            ),
            "returns": upsert_daily_rows(
                session,
                ReturnReviewDaily,
                _parse_sample_file(
                    sample_dir / "returns_reviews.csv",
                    required_columns={"SKU": "sku", "Date": "date"},
                    optional_columns={
                        "Return Count": "return_count",
                        "Return Reason": "return_reason",
                        "Negative Reviews": "negative_reviews",
                        "Rating": "rating",
                    },
                ),
            ),
        }
        run_result = _run_daily_analysis(
            run_date=date(2026, 1, 7),
            session=session,
            feishu_enabled=feishu_enabled,
        )
        return {**run_result, "imported": imported}

    @app.post("/imports/sales")
    async def import_sales(
        file: Annotated[UploadFile, File()],
        session: Session = Depends(get_session),
    ) -> dict:
        rows = await _parse_upload(
            file,
            required_columns={"SKU": "sku", "Date": "date", "Units Sold": "units_sold"},
            optional_columns={"Sales Amount": "sales_amount"},
        )
        return {"imported": upsert_daily_rows(session, SalesDaily, rows)}

    @app.post("/imports/ads")
    async def import_ads(
        file: Annotated[UploadFile, File()],
        session: Session = Depends(get_session),
    ) -> dict:
        rows = await _parse_upload(
            file,
            required_columns={"SKU": "sku", "Date": "date"},
            optional_columns={
                "Impressions": "impressions",
                "Clicks": "clicks",
                "Spend": "spend",
                "Ad Orders": "ad_orders",
                "Ad Sales": "ad_sales",
            },
        )
        return {"imported": upsert_daily_rows(session, AdsDaily, rows)}

    @app.post("/imports/inventory")
    async def import_inventory(
        file: Annotated[UploadFile, File()],
        session: Session = Depends(get_session),
    ) -> dict:
        rows = await _parse_upload(
            file,
            required_columns={"SKU": "sku", "Date": "date"},
            optional_columns={
                "Available Inventory": "available_inventory",
                "Inbound Inventory": "inbound_inventory",
                "Reserved Inventory": "reserved_inventory",
            },
        )
        return {"imported": upsert_daily_rows(session, InventoryDaily, rows)}

    @app.post("/imports/profit")
    async def import_profit(
        file: Annotated[UploadFile, File()],
        session: Session = Depends(get_session),
    ) -> dict:
        rows = await _parse_upload(
            file,
            required_columns={"SKU": "sku", "Date": "date"},
            optional_columns={
                "Product Cost": "product_cost",
                "Platform Fees": "platform_fees",
                "Logistics Fees": "logistics_fees",
                "Ad Spend": "ad_spend",
            },
        )
        return {"imported": upsert_daily_rows(session, ProfitDaily, rows)}

    @app.post("/imports/returns")
    async def import_returns(
        file: Annotated[UploadFile, File()],
        session: Session = Depends(get_session),
    ) -> dict:
        rows = await _parse_upload(
            file,
            required_columns={"SKU": "sku", "Date": "date"},
            optional_columns={
                "Return Count": "return_count",
                "Return Reason": "return_reason",
                "Negative Reviews": "negative_reviews",
                "Rating": "rating",
            },
        )
        return {"imported": upsert_daily_rows(session, ReturnReviewDaily, rows)}

    @app.post("/jobs/daily-run")
    def daily_run(
        run_date: date,
        session: Session = Depends(get_session),
    ) -> dict:
        return _run_daily_analysis(
            run_date=run_date,
            session=session,
            feishu_enabled=feishu_enabled,
        )

    @app.delete("/jobs/daily-run")
    def reset_daily_run(
        run_date: date,
        session: Session = Depends(get_session),
    ) -> dict:
        return {"date": run_date.isoformat(), **delete_daily_run_outputs(session, run_date)}

    @app.get("/metrics/daily")
    def get_metrics_daily(
        date: date,
        session: Session = Depends(get_session),
    ) -> list[dict]:
        return list_metrics(session, date)

    @app.get("/alerts")
    def get_alerts(
        session: Session = Depends(get_session),
        date: date | None = None,
    ) -> list[dict]:
        return list_alerts(session, date)

    @app.patch("/alerts/{alert_id}")
    def patch_alert(
        alert_id: int,
        payload: AlertUpdate,
        session: Session = Depends(get_session),
    ) -> dict:
        alert = update_alert_status(session, alert_id, payload.status)
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        return {"id": alert.id, "status": alert.status}

    @app.get("/reports/daily")
    def get_report_daily(
        date: date,
        session: Session = Depends(get_session),
    ) -> dict:
        report = get_daily_report(session, date)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        return report

    # 聊天 Agent
    chat_tools = ChatTools(session_factory)
    llm_client = build_llm_client(os.environ)
    chat_graph = ChatGraph(llm_client, chat_tools)

    @app.post("/chat")
    async def chat_endpoint(req: ChatRequest):
        """聊天端点 - SSE 流式响应"""
        import json

        async def event_stream():
            try:
                async for event in chat_graph.chat_stream(req.message, req.conversation_id):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/chat/history")
    def get_chat_history(conversation_id: str = "default") -> dict:
        """获取聊天历史（简单实现）"""
        return {"conversation_id": conversation_id, "messages": []}

    # ==================== 设置 API ====================

    class EccangSettings(BaseModel):
        app_key: str
        app_secret: str
        base_url: str = "https://open.eccang.com"

    class AmazonSettings(BaseModel):
        seller_id: str
        marketplace: str = "US"
        refresh_token: str
        client_id: str = ""
        client_secret: str = ""

    @app.get("/api/settings")
    def get_settings() -> dict:
        """获取当前设置（脱敏）"""
        return {
            "eccang": {
                "app_key": os.getenv("ECCANG_APP_KEY", ""),
                "app_secret": "***" if os.getenv("ECCANG_APP_SECRET") else "",
                "base_url": os.getenv("ECCANG_BASE_URL", "https://open.eccang.com"),
                "connected": bool(os.getenv("ECCANG_APP_KEY")),
            },
            "amazon": {
                "seller_id": os.getenv("AMAZON_SELLER_ID", ""),
                "marketplace": os.getenv("AMAZON_MARKETPLACE", "US"),
                "refresh_token": "***" if os.getenv("AMAZON_REFRESH_TOKEN") else "",
                "connected": bool(os.getenv("AMAZON_SELLER_ID")),
            },
        }

    @app.post("/api/settings/eccang")
    def save_eccang_settings(settings: EccangSettings) -> dict:
        """保存易仓设置"""
        _update_env_file({
            "ECCANG_APP_KEY": settings.app_key,
            "ECCANG_APP_SECRET": settings.app_secret,
            "ECCANG_BASE_URL": settings.base_url,
        })
        return {"success": True, "message": "易仓设置已保存"}

    @app.post("/api/settings/amazon")
    def save_amazon_settings(settings: AmazonSettings) -> dict:
        """保存亚马逊设置"""
        _update_env_file({
            "AMAZON_SELLER_ID": settings.seller_id,
            "AMAZON_MARKETPLACE": settings.marketplace,
            "AMAZON_REFRESH_TOKEN": settings.refresh_token,
            "AMAZON_CLIENT_ID": settings.client_id,
            "AMAZON_CLIENT_SECRET": settings.client_secret,
        })
        return {"success": True, "message": "亚马逊设置已保存"}

    @app.post("/api/settings/eccang/test")
    def test_eccang_connection() -> dict:
        """测试易仓连接"""
        app_key = os.getenv("ECCANG_APP_KEY", "")
        app_secret = os.getenv("ECCANG_APP_SECRET", "")
        base_url = os.getenv("ECCANG_BASE_URL", "https://open.eccang.com")

        if not app_key or not app_secret:
            return {"success": False, "message": "请先配置易仓API凭证"}

        client = EccangClient(
            app_key=app_key,
            app_secret=app_secret,
            base_url=base_url,
        )
        result = client.test_connection()
        client.close()
        return result

    # ==================== 战场地图 & 运营天眼 ====================

    battlefield_analyzer = BattlefieldAnalyzer()
    diagnosis_analyzer = DiagnosisAnalyzer()

    @app.get("/api/battlefield/analyze")
    def analyze_battlefield(asin: str, marketplace: str = "US") -> dict:
        """分析竞品，生成战场地图"""
        # 使用演示数据（实际应从数据库或 API 获取）
        return battlefield_analyzer.generate_demo_data(asin)

    @app.get("/api/battlefield/data/{asin}")
    def get_battlefield_data(asin: str) -> dict:
        """获取战场地图数据"""
        # 从数据库获取已分析的数据
        return {"asin": asin, "message": "请先运行分析"}

    @app.get("/api/diagnosis/run")
    def run_diagnosis(asin: str) -> dict:
        """运行产品诊断"""
        # 使用演示数据（实际应从数据库获取指标）
        return diagnosis_analyzer.generate_demo_data(asin)

    @app.get("/api/diagnosis/report/{asin}")
    def get_diagnosis_report(asin: str) -> dict:
        """获取诊断报告"""
        # 从数据库获取已生成的报告
        return {"asin": asin, "message": "请先运行诊断"}

    # ==================== 自动化任务 ====================

    # 注册任务处理器
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

    @app.get("/api/automation/tasks")
    def get_automation_tasks() -> list[dict]:
        """获取所有自动化任务"""
        return scheduler.get_all_tasks()

    @app.get("/api/automation/tasks/{task_id}")
    def get_automation_task(task_id: str) -> dict:
        """获取单个自动化任务"""
        task = scheduler.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        return task.to_dict()

    @app.post("/api/automation/tasks/{task_id}/enable")
    def enable_automation_task(task_id: str) -> dict:
        """启用任务"""
        task = scheduler.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        scheduler.enable_task(task_id)
        return {"success": True, "message": f"任务 {task.name} 已启用"}

    @app.post("/api/automation/tasks/{task_id}/disable")
    def disable_automation_task(task_id: str) -> dict:
        """禁用任务"""
        task = scheduler.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        scheduler.disable_task(task_id)
        return {"success": True, "message": f"任务 {task.name} 已禁用"}

    @app.post("/api/automation/tasks/{task_id}/run")
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

    class AutomationTaskUpdate(BaseModel):
        schedule_time: str | None = None
        enabled: bool | None = None
        config: dict | None = None

    @app.patch("/api/automation/tasks/{task_id}")
    def update_automation_task(task_id: str, payload: AutomationTaskUpdate) -> dict:
        """更新任务配置"""
        task = scheduler.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        if payload.schedule_time is not None:
            from datetime import time as dt_time
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

    return app


async def _parse_upload(
    file: UploadFile,
    *,
    required_columns: dict[str, str],
    optional_columns: dict[str, str],
) -> list[dict]:
    content = await file.read()
    try:
        return parse_tabular_upload(
            filename=file.filename or "",
            content=content,
            required_columns=required_columns,
            optional_columns=optional_columns,
        )
    except ImportValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _parse_sample_file(
    path: Path,
    *,
    required_columns: dict[str, str],
    optional_columns: dict[str, str],
) -> list[dict]:
    try:
        return parse_tabular_upload(
            filename=path.name,
            content=path.read_bytes(),
            required_columns=required_columns,
            optional_columns=optional_columns,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=f"Sample file not found: {path.name}") from exc
    except ImportValidationError as exc:
        raise HTTPException(status_code=500, detail=f"Invalid sample file {path.name}: {exc}") from exc


def _run_daily_analysis(
    *,
    run_date: date,
    session: Session,
    feishu_enabled: bool,
) -> dict:
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


def _update_env_file(updates: dict[str, str]) -> None:
    """更新 .env 文件"""
    env_path = Path.cwd() / ".env"
    lines = []
    existing_keys = set()

    # 读取现有内容
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key = line.split("=", 1)[0]
                    if key in updates:
                        lines.append(f"{key}={updates[key]}")
                        existing_keys.add(key)
                    else:
                        lines.append(line)
                else:
                    lines.append(line)

    # 添加新键
    for key, value in updates.items():
        if key not in existing_keys:
            lines.append(f"{key}={value}")

    # 写入文件
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # 更新当前环境变量
    for key, value in updates.items():
        os.environ[key] = value


app = create_app(database_url=os.getenv("DATABASE_URL", "sqlite+pysqlite:///./amazon_agent.db"))
