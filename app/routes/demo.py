"""演示数据路由"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_session
from app.db.models import AdsDaily, InventoryDaily, ProfitDaily, ReturnReviewDaily, SalesDaily
from app.db.repository import upsert_daily_rows, upsert_sku_rows
from app.importers.tabular import ImportValidationError, parse_tabular_upload
from app.services.daily_analysis import run_daily_analysis

router = APIRouter(tags=["演示"])
_feishu_enabled = True


def init_demo_config(*, feishu_enabled: bool) -> None:
    global _feishu_enabled
    _feishu_enabled = feishu_enabled


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


@router.post("/demo/load-sample")
def load_sample_demo(session: Session = Depends(get_session)) -> dict:
    """加载示例数据并运行分析"""
    sample_dir = Path(__file__).resolve().parent.parent.parent / "sample_data"
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
    run_result = run_daily_analysis(
        run_date=date(2026, 1, 7),
        session=session,
        feishu_enabled=_feishu_enabled,
    )
    return {**run_result, "imported": imported}
