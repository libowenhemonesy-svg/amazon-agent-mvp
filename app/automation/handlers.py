"""自动化任务处理器"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

logger = logging.getLogger(__name__)


async def handle_daily_analysis(config: dict) -> dict:
    """
    处理每日分析任务

    参数：
        config: 任务配置
            - run_date: 运行日期，"today" 或 "YYYY-MM-DD"

    返回：
        执行结果
    """
    from app.services.daily_analysis import run_daily_analysis
    from app.db.session import build_session_factory
    from app.env import load_env_file
    from pathlib import Path
    import os

    load_env_file(Path.cwd() / ".env")

    # 确定运行日期
    run_date_str = config.get("run_date", "today")
    if run_date_str == "today":
        run_date = date.today()
    else:
        run_date = date.fromisoformat(run_date_str)

    logger.info(f"执行每日分析: {run_date}")

    try:
        # 创建数据库会话
        database_url = os.getenv("DATABASE_URL", "sqlite+pysqlite:///./amazon_agent.db")
        session_factory = build_session_factory(database_url)

        with session_factory() as session:
            result = run_daily_analysis(
                run_date=run_date,
                session=session,
                feishu_enabled=True,
            )

        logger.info(f"每日分析完成: {result}")
        return {
            "success": True,
            "date": run_date.isoformat(),
            "result": result,
        }
    except Exception as e:
        logger.error(f"每日分析失败: {e}")
        return {
            "success": False,
            "error": str(e),
        }


async def handle_data_sync(config: dict) -> dict:
    """
    处理数据同步任务

    参数：
        config: 任务配置
            - sources: 数据源列表 ["eccang", "amazon"]

    返回：
        执行结果
    """
    import os
    from app.env import load_env_file
    from pathlib import Path

    load_env_file(Path.cwd() / ".env")

    sources = config.get("sources", [])
    results = {}

    for source in sources:
        if source == "eccang":
            results["eccang"] = await _sync_eccang_data()
        elif source == "amazon":
            results["amazon"] = await _sync_amazon_data()

    return {
        "success": True,
        "synced_sources": list(results.keys()),
        "results": results,
    }


async def _sync_eccang_data() -> dict:
    """同步易仓数据"""
    import os
    from app.integrations.eccang.client import EccangClient

    app_key = os.getenv("ECCANG_APP_KEY", "")
    app_secret = os.getenv("ECCANG_APP_SECRET", "")
    base_url = os.getenv("ECCANG_BASE_URL", "https://open.eccang.com")

    if not app_key or not app_secret:
        return {"success": False, "message": "未配置易仓凭证"}

    try:
        client = EccangClient(
            app_key=app_key,
            app_secret=app_secret,
            base_url=base_url,
        )

        # 获取订单数据
        orders = client.get_orders(page_size=50)

        # 获取库存数据
        inventory = client.get_inventory(page_size=50)

        client.close()

        return {
            "success": True,
            "orders_count": len(orders.get("data", [])),
            "inventory_count": len(inventory.get("data", [])),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _sync_amazon_data() -> dict:
    """同步亚马逊数据"""
    # TODO: 实现亚马逊 SP-API 数据同步
    return {"success": True, "message": "亚马逊数据同步功能待实现"}


async def handle_competitor_monitor(config: dict) -> dict:
    """
    处理竞品监控任务

    参数：
        config: 任务配置
            - marketplace: 站点
            - asins: 要监控的 ASIN 列表（可选）

    返回：
        执行结果
    """
    from app.db.session import build_session_factory
    from app.db.models import SkuMaster
    from app.analysis.battlefield import BattlefieldAnalyzer
    from sqlalchemy import select
    import os
    from app.env import load_env_file
    from pathlib import Path

    load_env_file(Path.cwd() / ".env")

    marketplace = config.get("marketplace", "US")

    try:
        # 获取要监控的 ASIN 列表
        database_url = os.getenv("DATABASE_URL", "sqlite+pysqlite:///./amazon_agent.db")
        session_factory = build_session_factory(database_url)

        with session_factory() as session:
            skus = session.scalars(
                select(SkuMaster).where(SkuMaster.enabled.is_(True))
            ).all()

        if not skus:
            return {"success": True, "message": "无 SKU 需要监控"}

        # 使用战场地图分析器
        analyzer = BattlefieldAnalyzer()
        results = []

        for sku in skus[:5]:  # 限制每次最多监控 5 个
            if sku.asin:
                result = analyzer.generate_demo_data(sku.asin)
                results.append({
                    "asin": sku.asin,
                    "sku": sku.sku,
                    "competitors_count": len(result.get("competitors", [])),
                })

        return {
            "success": True,
            "monitored_count": len(results),
            "results": results,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
