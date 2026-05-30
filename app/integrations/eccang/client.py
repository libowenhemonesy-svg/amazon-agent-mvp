"""易仓ERP API 客户端"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime
from typing import Any, Optional

import httpx


class EccangClient:
    """易仓ERP API 客户端"""

    def __init__(
        self,
        app_key: str,
        app_secret: str,
        base_url: str = "https://open.eccang.com",
        timeout: float = 30.0,
    ):
        self.app_key = app_key
        self.app_secret = app_secret
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)

    def _generate_sign(self, params: dict[str, Any]) -> str:
        """生成API签名"""
        # 按参数名排序
        sorted_params = sorted(params.items())
        # 拼接字符串
        sign_str = "&".join(f"{k}={v}" for k, v in sorted_params)
        # 使用 HMAC-MD5 生成签名
        sign = hmac.new(
            self.app_secret.encode("utf-8"),
            sign_str.encode("utf-8"),
            hashlib.md5,
        ).hexdigest().upper()
        return sign

    def _build_common_params(self) -> dict[str, Any]:
        """构建公共参数"""
        return {
            "app_key": self.app_key,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "format": "json",
            "v": "1.0",
        }

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """发送API请求"""
        # 构建公共参数
        common_params = self._build_common_params()

        # 合并参数
        if params:
            common_params.update(params)

        # 生成签名
        common_params["sign"] = self._generate_sign(common_params)

        # 发送请求
        url = f"{self.base_url}{path}"

        if method.upper() == "GET":
            response = self.client.get(url, params=common_params)
        else:
            response = self.client.post(url, params=common_params, json=data)

        response.raise_for_status()
        return response.json()

    # ==================== 订单相关 ====================

    def get_orders(
        self,
        status: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """获取订单列表"""
        params = {
            "page_no": page,
            "page_size": page_size,
        }
        if status:
            params["status"] = status
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        return self._request("GET", "/api/order/list", params=params)

    def get_order_detail(self, order_no: str) -> dict[str, Any]:
        """获取订单详情"""
        return self._request("GET", "/api/order/detail", params={"order_no": order_no})

    # ==================== 库存相关 ====================

    def get_inventory(
        self,
        sku: Optional[str] = None,
        warehouse_code: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """获取库存列表"""
        params = {
            "page_no": page,
            "page_size": page_size,
        }
        if sku:
            params["sku"] = sku
        if warehouse_code:
            params["warehouse_code"] = warehouse_code

        return self._request("GET", "/api/inventory/list", params=params)

    def get_inventory_detail(self, sku: str) -> dict[str, Any]:
        """获取库存详情"""
        return self._request("GET", "/api/inventory/detail", params={"sku": sku})

    # ==================== 商品相关 ====================

    def get_products(
        self,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """获取商品列表"""
        params = {
            "page_no": page,
            "page_size": page_size,
        }
        if keyword:
            params["keyword"] = keyword

        return self._request("GET", "/api/product/list", params=params)

    def get_product_detail(self, sku: str) -> dict[str, Any]:
        """获取商品详情"""
        return self._request("GET", "/api/product/detail", params={"sku": sku})

    # ==================== 物流相关 ====================

    def get_shipments(
        self,
        status: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """获取发货单列表"""
        params = {
            "page_no": page,
            "page_size": page_size,
        }
        if status:
            params["status"] = status
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        return self._request("GET", "/api/shipment/list", params=params)

    def get_tracking(self, tracking_no: str) -> dict[str, Any]:
        """获取物流跟踪信息"""
        return self._request("GET", "/api/tracking/detail", params={"tracking_no": tracking_no})

    # ==================== 仓库相关 ====================

    def get_warehouses(self) -> dict[str, Any]:
        """获取仓库列表"""
        return self._request("GET", "/api/warehouse/list")

    # ==================== 工具方法 ====================

    def test_connection(self) -> dict[str, Any]:
        """测试API连接"""
        try:
            result = self.get_warehouses()
            return {
                "success": True,
                "message": "连接成功",
                "data": result,
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"连接失败: {str(e)}",
            }

    def close(self):
        """关闭客户端"""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
