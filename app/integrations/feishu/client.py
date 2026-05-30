from __future__ import annotations

from typing import Protocol

import httpx


class JsonTransport(Protocol):
    def post_json(self, url: str, payload: dict, headers: dict[str, str]) -> dict:
        ...


class HttpxTransport:
    def post_json(self, url: str, payload: dict, headers: dict[str, str]) -> dict:
        response = httpx.post(url, json=payload, headers=headers, timeout=20)
        response.raise_for_status()
        return response.json()


class FeishuClient:
    def __init__(
        self,
        *,
        app_token: str,
        table_ids: dict[str, str],
        access_token: str,
        transport: JsonTransport | None = None,
    ) -> None:
        self.app_token = app_token
        self.table_ids = table_ids
        self.access_token = access_token
        self.transport = transport or HttpxTransport()

    @staticmethod
    def get_tenant_access_token(
        *,
        app_id: str,
        app_secret: str,
        transport: JsonTransport | None = None,
    ) -> str:
        auth_transport = transport or HttpxTransport()
        result = auth_transport.post_json(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            {"app_id": app_id, "app_secret": app_secret},
            {"Content-Type": "application/json; charset=utf-8"},
        )
        if result.get("code", 0) != 0:
            raise RuntimeError(f"Feishu auth error: {result}")
        return result.get("tenant_access_token", "")

    def upsert_record(self, *, table_name: str, unique_key: str, fields: dict) -> str:
        table_id = self.table_ids[table_name]
        url = (
            "https://open.feishu.cn/open-apis/bitable/v1/apps/"
            f"{self.app_token}/tables/{table_id}/records"
        )
        payload = {"fields": {"unique_key": unique_key, **fields}}
        result = self.transport.post_json(url, payload, self._headers())
        if result.get("code", 0) != 0:
            raise RuntimeError(f"Feishu API error: {result}")
        return result.get("data", {}).get("record", {}).get("record_id", "")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=utf-8",
        }
