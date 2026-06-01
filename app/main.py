from __future__ import annotations

import os
from collections.abc import Generator
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import Body, Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.agents.graph import build_ops_graph
from app.agents.llm import build_llm_client
from app.agents.chat_graph import ChatGraph
from app.agents.tools import ChatTools
from app.analysis.battlefield import BattlefieldAnalyzer
from app.analysis.diagnosis import DiagnosisAnalyzer
from app.analysis.product_research import ProductResearchAnalyzer
from app.automation.scheduler import AutomationScheduler, AutomationTask, TaskType, TaskStatus, init_default_tasks, scheduler
from app.automation.handlers import handle_daily_analysis, handle_data_sync, handle_competitor_monitor
from app.integrations.eccang.client import EccangClient
from app.db.models import AdsDaily, Base, InventoryDaily, ProfitDaily, ReturnReviewDaily, SalesDaily, SkuMaster
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


from fastapi.middleware.cors import CORSMiddleware

load_env_file(Path.cwd() / ".env")


class AlertUpdate(BaseModel):
    status: str


class ChatRequest(BaseModel):
    message: str
    conversation_id: str = "default"


class ProductResearchRequest(BaseModel):
    keyword: str
    marketplace: str = "US"
    category: str = "all"


class ChromeProductData(BaseModel):
    """Chrome 插件提取的商品数据"""
    title: str = ""
    price: str = ""
    rating: str = ""
    review_count: str = ""
    bullets: list[str] = []
    url: str = ""
    asin: str = ""
    reviews: list[dict] = []


ChromeProductData.model_rebuild()


def create_app(
    *,
    database_url: str = "sqlite+pysqlite:///./amazon_agent.db",
    feishu_enabled: bool = True,
    product_research_ai_enabled: bool = True,
) -> FastAPI:
    session_factory = build_session_factory(database_url)
    Base.metadata.create_all(session_factory.kw["bind"])
    ensure_sqlite_dev_schema(session_factory.kw["bind"])

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
    product_research_analyzer = ProductResearchAnalyzer()

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

    @app.post("/api/selection/research")
    def run_product_research(
        payload: ProductResearchRequest,
        session: Session = Depends(get_session),
    ) -> dict:
        """基于 Chrome 采集商品池运行关键词选品研究。"""
        keyword = payload.keyword.strip()
        if not keyword:
            raise HTTPException(status_code=400, detail="关键词不能为空")

        marketplace = (payload.marketplace or "US").upper()
        category = payload.category or "all"
        rows = session.scalars(select(SkuMaster).where(SkuMaster.store == "Amazon")).all()
        competitors = []
        for sku in rows:
            row_marketplace = (sku.marketplace or "US").upper()
            if row_marketplace != marketplace:
                continue
            if category != "all" and (sku.product_category or "").lower() != category.lower():
                continue
            competitors.append({
                "sku": sku.sku,
                "asin": sku.asin or sku.sku,
                "title": sku.title or sku.asin or sku.sku,
                "price": sku.price or 0,
                "rating": sku.rating or 0,
                "review_count": sku.review_count or 0,
                "url": sku.platform_link or "",
                "marketplace": row_marketplace,
                "category": sku.product_category or "",
            })

        return product_research_analyzer.analyze(
            keyword=keyword,
            marketplace=marketplace,
            category=category,
            competitors=competitors,
            llm_client=build_llm_client(os.environ) if product_research_ai_enabled else None,
        )

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

    # ==================== Chrome 插件数据接收 ====================

    @app.post("/api/chrome/submit")
    async def submit_chrome_data(request: Request) -> dict:
        """接收 Chrome 插件提取的商品数据"""
        try:
            body = await request.json()
            title = body.get("title", "")
            price_raw = body.get("price", "")
            rating_raw = body.get("rating", "")
            review_count_raw = body.get("review_count", "")
            bullets = body.get("bullets", [])
            image = body.get("image", "")
            url = body.get("url", "")
            asin = body.get("asin", "")
            reviews = body.get("reviews", [])

            # 解析价格
            price_str = price_raw.replace("$", "").replace(",", "").strip()
            try:
                price = float(price_str) if price_str else 0
            except ValueError:
                price = 0

            # 解析评分
            rating_str = rating_raw.split()[0] if rating_raw else "0"
            try:
                rating = float(rating_str) if rating_str else 0
            except ValueError:
                rating = 0

            # 解析评论数
            review_str = review_count_raw.replace(",", "").split()[0] if review_count_raw else "0"
            try:
                review_count = int(review_str) if review_str else 0
            except ValueError:
                review_count = 0

            # 保存到数据库
            with session_factory() as session:
                if asin:
                    existing = session.scalar(
                        select(SkuMaster).where(SkuMaster.asin == asin)
                    )

                    if existing:
                        # 更新已有记录
                        existing.title = title or existing.title
                        existing.price = price if price else existing.price
                        existing.rating = rating if rating else existing.rating
                        existing.review_count = review_count if review_count else existing.review_count
                        existing.main_image = image or existing.main_image
                        existing.platform_link = url or existing.platform_link
                    else:
                        # 创建新记录
                        new_sku = SkuMaster(
                            sku=asin,
                            asin=asin,
                            title=title,
                            price=price,
                            rating=rating,
                            review_count=review_count,
                            main_image=image,
                            platform_link=url,
                            store="Amazon",
                            marketplace="US",
                            product_category="",
                            lifecycle="new",
                        )
                        session.add(new_sku)

                    session.commit()

            return {
                "success": True,
                "message": "数据已保存",
                "asin": asin,
                "price": price,
                "rating": rating,
                "review_count": review_count,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @app.get("/api/chrome/products")
    def get_chrome_products() -> dict:
        """获取通过 Chrome 插件提交的商品列表"""
        with session_factory() as session:
            skus = session.scalars(
                select(SkuMaster).where(SkuMaster.store == "Amazon").limit(50)
            ).all()

            products = []
            for sku in skus:
                products.append({
                    "asin": sku.asin or sku.sku,
                    "title": sku.title or sku.asin or sku.sku,
                    "price": sku.price or 0,
                    "rating": sku.rating or 0,
                    "review_count": sku.review_count or 0,
                    "main_image": sku.main_image or "",
                    "url": sku.platform_link or "",
                    "marketplace": sku.marketplace or "US",
                })

            return {"products": products}

    @app.delete("/api/chrome/products/{asin}")
    def delete_chrome_product(asin: str) -> dict:
        """删除 Chrome 插件采集的商品"""
        try:
            with session_factory() as session:
                sku = session.scalar(
                    select(SkuMaster).where(SkuMaster.asin == asin)
                )
                if not sku:
                    return {"success": False, "error": "商品不存在"}

                session.delete(sku)
                session.commit()
                return {"success": True, "message": f"已删除 {asin}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @app.delete("/api/chrome/products")
    def delete_multiple_products(request: Request) -> dict:
        """批量删除商品"""
        # 需要从请求体获取 ASIN 列表
        # FastAPI 的 DELETE 不支持 Body，改用 POST
        pass

    @app.post("/api/chrome/products/delete-batch")
    async def delete_batch_products(request: Request) -> dict:
        """批量删除商品"""
        try:
            body = await request.json()
            asins = body.get("asins", [])
            if not asins:
                return {"success": False, "error": "未选择商品"}

            deleted = 0
            with session_factory() as session:
                for asin in asins:
                    sku = session.scalar(
                        select(SkuMaster).where(SkuMaster.asin == asin)
                    )
                    if sku:
                        session.delete(sku)
                        deleted += 1
                session.commit()

            return {"success": True, "message": f"已删除 {deleted} 个商品", "deleted": deleted}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== AI 商品分析 ====================

    @app.post("/api/chrome/analyze")
    async def analyze_products(request: Request) -> dict:
        """AI 分析选中的商品"""
        try:
            body = await request.json()
            asins = body.get("asins", [])

            # 获取商品数据
            products = []
            with session_factory() as session:
                for asin in asins:
                    sku = session.scalar(
                        select(SkuMaster).where(SkuMaster.asin == asin)
                    )
                    if sku:
                        products.append({
                            "asin": sku.asin,
                            "title": sku.title or "",
                            "price": sku.price or 0,
                            "rating": sku.rating or 0,
                            "review_count": sku.review_count or 0,
                        })

            if not products:
                return {"success": False, "error": "未找到商品数据"}

            # 构建分析提示词
            product_info = "\n".join([
                f"- ASIN: {p['asin']}, 标题: {p['title']}, 价格: ${p['price']}, 评分: {p['rating']}★, 评论数: {p['review_count']}"
                for p in products
            ])

            prompt = f"""你是一位资深亚马逊选品专家。请分析以下商品数据，给出专业的选品建议。

商品数据：
{product_info}

请从以下维度分析并给出结论：
1. 市场潜力（价格区间、需求量）
2. 竞争程度（评分分布、评论数量）
3. 利润空间（定价建议）
4. 风险提示（退货率、差评关键词）
5. 综合推荐指数（0-100分）

请用简洁的中文回答，使用 JSON 格式返回：
{{
  "score": 推荐指数,
  "summary": "一句话总结",
  "market_potential": "市场潜力分析",
  "competition": "竞争程度分析",
  "profit_advice": "利润建议",
  "risks": ["风险1", "风险2"],
  "suggestions": ["建议1", "建议2"]
}}"""

            # 调用 AI 分析
            from openai import OpenAI
            client = OpenAI(
                api_key=os.getenv("DEEPSEEK_API_KEY", ""),
                base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            )

            response = client.chat.completions.create(
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                messages=[
                    {"role": "system", "content": "你是亚马逊选品分析专家，返回 JSON 格式的分析结果。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000,
            )

            ai_text = response.choices[0].message.content.strip()

            # 解析 JSON
            import json
            # 提取 JSON 部分
            if "```json" in ai_text:
                ai_text = ai_text.split("```json")[1].split("```")[0].strip()
            elif "```" in ai_text:
                ai_text = ai_text.split("```")[1].split("```")[0].strip()

            try:
                result = json.loads(ai_text)
            except json.JSONDecodeError:
                result = {
                    "score": 70,
                    "summary": ai_text[:200],
                    "market_potential": "需要更多数据",
                    "competition": "中等",
                    "profit_advice": "建议优化定价",
                    "risks": ["数据不足"],
                    "suggestions": ["补充更多商品信息"]
                }

            return {"success": True, "analysis": result, "product_count": len(products)}

        except Exception as e:
            return {"success": False, "error": str(e)}

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
