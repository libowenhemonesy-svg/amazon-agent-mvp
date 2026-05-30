"""聊天 Agent 工具函数 - 查询数据库"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.models import (
    SkuMaster,
    SalesDaily,
    AdsDaily,
    InventoryDaily,
    ProfitDaily,
    ReturnReviewDaily,
    AlertTask,
    SkuMetricsDaily,
)


def _session_factory(db_url: str):
    """创建数据库会话工厂"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(db_url)
    return sessionmaker(bind=engine)


class ChatTools:
    """聊天工具集合"""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def _get_session(self) -> Session:
        return self.session_factory()

    def query_sku_list(self, keyword: Optional[str] = None) -> str:
        """查询SKU列表。可按关键词过滤（SKU、ASIN、店铺名称）。"""
        session = self._get_session()
        try:
            stmt = select(SkuMaster).where(SkuMaster.enabled.is_(True))
            if keyword:
                keyword = keyword.lower()
                stmt = stmt.where(
                    SkuMaster.sku.ilike(f"%{keyword}%")
                    | SkuMaster.asin.ilike(f"%{keyword}%")
                    | SkuMaster.store.ilike(f"%{keyword}%")
                )
            rows = session.scalars(stmt.limit(20)).all()
            if not rows:
                return json.dumps({"message": "未找到匹配的SKU"}, ensure_ascii=False)

            result = []
            for row in rows:
                result.append({
                    "sku": row.sku,
                    "asin": row.asin,
                    "store": row.store,
                    "marketplace": row.marketplace,
                    "lifecycle": row.lifecycle,
                })
            return json.dumps({"count": len(result), "skus": result}, ensure_ascii=False)
        finally:
            session.close()

    def query_sales(self, sku: Optional[str] = None, days: int = 7) -> str:
        """查询销售数据。参数: sku(可选), days(默认7天)。返回销量、销售额、排名等。"""
        session = self._get_session()
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            stmt = select(SalesDaily).where(SalesDaily.date >= start_date, SalesDaily.date <= end_date)
            if sku:
                stmt = stmt.where(SalesDaily.sku == sku)

            rows = session.scalars(stmt.order_by(SalesDaily.sales_amount.desc()).limit(20)).all()
            if not rows:
                return json.dumps({"message": f"最近{days}天无销售数据"}, ensure_ascii=False)

            result = []
            for row in rows:
                result.append({
                    "sku": row.sku,
                    "date": row.date.isoformat(),
                    "units_sold": row.units_sold,
                    "sales_amount": row.sales_amount,
                })

            # 汇总统计
            total_units = sum(r.units_sold or 0 for r in rows)
            total_sales = sum(r.sales_amount or 0 for r in rows)

            return json.dumps({
                "period": f"{start_date.isoformat()} ~ {end_date.isoformat()}",
                "total_units": total_units,
                "total_sales": round(total_sales, 2),
                "records": result,
            }, ensure_ascii=False)
        finally:
            session.close()

    def query_ads(self, sku: Optional[str] = None, days: int = 7) -> str:
        """查询广告数据。参数: sku(可选), days(默认7天)。返回ACOS、花费、点击等。"""
        session = self._get_session()
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            stmt = select(AdsDaily).where(AdsDaily.date >= start_date, AdsDaily.date <= end_date)
            if sku:
                stmt = stmt.where(AdsDaily.sku == sku)

            rows = session.scalars(stmt.order_by(AdsDaily.spend.desc()).limit(20)).all()
            if not rows:
                return json.dumps({"message": f"最近{days}天无广告数据"}, ensure_ascii=False)

            result = []
            for row in rows:
                result.append({
                    "sku": row.sku,
                    "date": row.date.isoformat(),
                    "impressions": row.impressions,
                    "clicks": row.clicks,
                    "spend": row.spend,
                    "ad_sales": row.ad_sales,
                    "acos": round(row.ad_sales / row.spend * 100, 2) if row.spend and row.ad_sales else None,
                })

            total_spend = sum(r.spend or 0 for r in rows)
            total_ad_sales = sum(r.ad_sales or 0 for r in rows)
            avg_acos = round(total_ad_sales / total_spend * 100, 2) if total_spend else 0

            return json.dumps({
                "period": f"{start_date.isoformat()} ~ {end_date.isoformat()}",
                "total_spend": round(total_spend, 2),
                "total_ad_sales": round(total_ad_sales, 2),
                "avg_acos": avg_acos,
                "records": result,
            }, ensure_ascii=False)
        finally:
            session.close()

    def query_inventory(self, sku: Optional[str] = None) -> str:
        """查询库存数据。参数: sku(可选)。返回可售、在途、预留库存。"""
        session = self._get_session()
        try:
            stmt = select(InventoryDaily).order_by(InventoryDaily.date.desc())
            if sku:
                stmt = stmt.where(InventoryDaily.sku == sku)

            rows = session.scalars(stmt.limit(20)).all()
            if not rows:
                return json.dumps({"message": "无库存数据"}, ensure_ascii=False)

            result = []
            for row in rows:
                result.append({
                    "sku": row.sku,
                    "date": row.date.isoformat(),
                    "available": row.available_inventory,
                    "inbound": row.inbound_inventory,
                    "reserved": row.reserved_inventory,
                })

            return json.dumps({"records": result}, ensure_ascii=False)
        finally:
            session.close()

    def query_alerts(self, status: Optional[str] = None, days: int = 7) -> str:
        """查询告警任务。参数: status(pending/processing/done/reviewed/ignored可选), days(默认7天)。"""
        session = self._get_session()
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            stmt = select(AlertTask).where(AlertTask.date >= start_date, AlertTask.date <= end_date)
            if status:
                stmt = stmt.where(AlertTask.status == status)

            rows = session.scalars(stmt.order_by(AlertTask.severity.desc()).limit(20)).all()
            if not rows:
                return json.dumps({"message": f"最近{days}天无告警任务"}, ensure_ascii=False)

            result = []
            for row in rows:
                result.append({
                    "id": row.id,
                    "sku": row.sku,
                    "alert_type": row.alert_type,
                    "severity": row.severity,
                    "reason": row.reason,
                    "status": row.status,
                    "date": row.date.isoformat(),
                })

            return json.dumps({
                "count": len(result),
                "alerts": result,
            }, ensure_ascii=False)
        finally:
            session.close()

    def query_profit(self, sku: Optional[str] = None, days: int = 30) -> str:
        """查询利润数据。参数: sku(可选), days(默认30天)。返回利润率、成本结构等。"""
        session = self._get_session()
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            stmt = select(ProfitDaily).where(ProfitDaily.date >= start_date, ProfitDaily.date <= end_date)
            if sku:
                stmt = stmt.where(ProfitDaily.sku == sku)

            rows = session.scalars(stmt.order_by(ProfitDaily.date.desc()).limit(20)).all()
            if not rows:
                return json.dumps({"message": f"最近{days}天无利润数据"}, ensure_ascii=False)

            result = []
            for row in rows:
                result.append({
                    "sku": row.sku,
                    "date": row.date.isoformat(),
                    "product_cost": row.product_cost,
                    "platform_fees": row.platform_fees,
                    "logistics_fees": row.logistics_fees,
                    "ad_spend": row.ad_spend,
                })

            return json.dumps({
                "period": f"{start_date.isoformat()} ~ {end_date.isoformat()}",
                "records": result,
            }, ensure_ascii=False)
        finally:
            session.close()

    def query_returns(self, sku: Optional[str] = None, days: int = 30) -> str:
        """查询退货数据。参数: sku(可选), days(默认30天)。返回退货率、退货原因等。"""
        session = self._get_session()
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            stmt = select(ReturnReviewDaily).where(
                ReturnReviewDaily.date >= start_date, ReturnReviewDaily.date <= end_date
            )
            if sku:
                stmt = stmt.where(ReturnReviewDaily.sku == sku)

            rows = session.scalars(stmt.order_by(ReturnReviewDaily.date.desc()).limit(20)).all()
            if not rows:
                return json.dumps({"message": f"最近{days}天无退货数据"}, ensure_ascii=False)

            result = []
            for row in rows:
                result.append({
                    "sku": row.sku,
                    "date": row.date.isoformat(),
                    "return_count": row.return_count,
                    "return_reason": row.return_reason,
                    "negative_reviews": row.negative_reviews,
                    "rating": row.rating,
                })

            return json.dumps({
                "period": f"{start_date.isoformat()} ~ {end_date.isoformat()}",
                "records": result,
            }, ensure_ascii=False)
        finally:
            session.close()

    def get_tools(self):
        """返回所有工具函数列表"""
        return [
            self.query_sku_list,
            self.query_sales,
            self.query_ads,
            self.query_inventory,
            self.query_alerts,
            self.query_profit,
            self.query_returns,
        ]
