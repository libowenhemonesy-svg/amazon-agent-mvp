"""数据导入路由"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.deps import get_session
from app.db.models import AdsDaily, InventoryDaily, ProfitDaily, ReturnReviewDaily, SalesDaily
from app.db.repository import upsert_daily_rows, upsert_sku_rows
from app.importers.tabular import ImportValidationError, parse_tabular_upload

router = APIRouter(prefix="/imports", tags=["数据导入"])


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


@router.post("/sku")
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


@router.post("/sales")
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


@router.post("/ads")
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


@router.post("/inventory")
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


@router.post("/profit")
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


@router.post("/returns")
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
