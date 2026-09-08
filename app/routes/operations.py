"""销售、广告和库存运营模块的领星 MCP 数据接口。"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_session
from app.integrations.lingxing import LingxingMcpProvider
from app.selection.contracts import McpCapability

router = APIRouter(prefix="/api", tags=["领星运营数据"])
provider = LingxingMcpProvider()


def _filters(
    days: int,
    end_date: date | None,
    store: str | None,
    marketplace: str | None,
    sku: str | None,
) -> dict[str, Any]:
    return {
        "days": days,
        "end_date": end_date.isoformat() if end_date else None,
        "store": store,
        "marketplace": marketplace,
        "sku": sku,
    }


@router.get("/operations/source-status")
def operations_source_status(session: Session = Depends(get_session)) -> dict[str, Any]:
    return provider.describe(session)


@router.get("/sales-monitor/dashboard")
async def sales_dashboard(
    days: int = Query(default=30, ge=1, le=365),
    end_date: date | None = None,
    store: str | None = None,
    marketplace: str | None = None,
    sku: str | None = None,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    filters = _filters(days, end_date, store, marketplace, sku)
    summary = await provider.call(session, McpCapability.SALES_SUMMARY, filters)
    trend = await provider.call(session, McpCapability.SALES_TREND, filters)
    return _dashboard_response(provider.describe(session), filters, summary=summary, trend=trend)


@router.get("/ads-analysis/dashboard")
async def ads_dashboard(
    days: int = Query(default=30, ge=1, le=365),
    end_date: date | None = None,
    store: str | None = None,
    marketplace: str | None = None,
    sku: str | None = None,
    level: str = Query(default="campaign", pattern="^(campaign|ad_group|target|search_term)$"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    filters = _filters(days, end_date, store, marketplace, sku) | {"level": level}
    performance = await provider.call(session, McpCapability.AD_PERFORMANCE, filters)
    entities = await provider.call(session, McpCapability.AD_ENTITIES, filters)
    return _dashboard_response(
        provider.describe(session), filters, performance=performance, entities=entities
    )


@router.get("/inventory-agent/dashboard")
async def inventory_dashboard(
    days: int = Query(default=30, ge=1, le=365),
    end_date: date | None = None,
    store: str | None = None,
    marketplace: str | None = None,
    sku: str | None = None,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    filters = _filters(days, end_date, store, marketplace, sku)
    snapshot = await provider.call(session, McpCapability.INVENTORY_SNAPSHOT, filters)
    replenishment = await provider.call(session, McpCapability.REPLENISHMENT_DATA, filters)
    return _dashboard_response(
        provider.describe(session), filters, snapshot=snapshot, replenishment=replenishment
    )


def _dashboard_response(source: dict, filters: dict, **datasets: dict) -> dict[str, Any]:
    timestamps = [
        dataset.get("source_updated_at")
        for dataset in datasets.values()
        if dataset.get("source_updated_at")
    ]
    source = dict(source)
    source["source_updated_at"] = max(timestamps) if timestamps else None
    return {"source": source, "filters": filters, **datasets}
