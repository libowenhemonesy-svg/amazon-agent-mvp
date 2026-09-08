"""MCP 数据源服务端凭据存储。"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping


class EnvCredentialStore:
    """通过稳定引用读写服务端环境变量，不向数据模型暴露凭据。"""

    def __init__(
        self,
        env: Mapping[str, str],
        updater: Callable[[dict[str, str]], None],
    ) -> None:
        self.env = env
        self.updater = updater

    def save(
        self,
        reference: str,
        *,
        api_key: str = "",
        headers: Mapping[str, str] | None = None,
    ) -> None:
        updates: dict[str, str] = {}
        normalized_key = api_key.strip()
        if normalized_key:
            updates[f"{reference}_API_KEY"] = normalized_key
        if headers:
            updates[f"{reference}_HEADERS"] = json.dumps(
                {str(key): str(value) for key, value in headers.items()},
                ensure_ascii=False,
            )
        if updates:
            self.updater(updates)

    def load_headers(self, reference: str) -> dict[str, str]:
        raw_headers = self.env.get(f"{reference}_HEADERS", "{}").strip() or "{}"
        parsed = json.loads(raw_headers)
        if not isinstance(parsed, dict):
            raise ValueError("MCP 自定义请求头必须是 JSON 对象")
        headers = {str(key): str(value) for key, value in parsed.items()}
        api_key = self.env.get(f"{reference}_API_KEY", "").strip()
        if api_key:
            headers.setdefault("Authorization", f"Bearer {api_key}")
        return headers

    def configured(self, reference: str) -> bool:
        return bool(
            self.env.get(f"{reference}_API_KEY", "").strip()
            or self.env.get(f"{reference}_HEADERS", "").strip()
        )
