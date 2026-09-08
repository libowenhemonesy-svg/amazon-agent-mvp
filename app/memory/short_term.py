from __future__ import annotations

import json
from typing import Any


class InMemoryShortTermMemory:
    """测试和未配置 Redis 时使用的短期记忆。"""

    def __init__(self, *, max_messages: int = 20) -> None:
        self.max_messages = max_messages
        self._recent_messages: dict[str, list[dict[str, str]]] = {}
        self._raw_data: dict[str, str] = {}

    def append_recent_message(self, conversation_id: str, role: str, content: str) -> None:
        rows = self._recent_messages.setdefault(conversation_id, [])
        rows.append({"role": role, "content": content})
        del rows[:-self.max_messages]

    def get_recent_messages(self, conversation_id: str, limit: int = 10) -> list[dict[str, str]]:
        rows = self._recent_messages.get(conversation_id, [])
        return rows[-limit:]

    def set_sellersprite_raw(self, conversation_id: str, raw_data: str) -> None:
        self._raw_data[conversation_id] = raw_data

    def get_sellersprite_raw(self, conversation_id: str) -> str | None:
        return self._raw_data.get(conversation_id)


class RedisShortTermMemory:
    """Redis 短期记忆：最近对话、临时原始数据。"""

    def __init__(
        self,
        client: Any,
        *,
        max_messages: int = 20,
        recent_ttl_seconds: int = 7 * 24 * 60 * 60,
        raw_ttl_seconds: int = 3 * 24 * 60 * 60,
    ) -> None:
        self.client = client
        self.max_messages = max_messages
        self.recent_ttl_seconds = recent_ttl_seconds
        self.raw_ttl_seconds = raw_ttl_seconds

    @classmethod
    def from_url(cls, redis_url: str) -> "RedisShortTermMemory":
        from redis import Redis

        return cls(Redis.from_url(redis_url, decode_responses=True))

    def append_recent_message(self, conversation_id: str, role: str, content: str) -> None:
        key = self._recent_key(conversation_id)
        payload = json.dumps({"role": role, "content": content}, ensure_ascii=False)
        self.client.rpush(key, payload)
        self.client.ltrim(key, -self.max_messages, -1)
        self.client.expire(key, self.recent_ttl_seconds)

    def get_recent_messages(self, conversation_id: str, limit: int = 10) -> list[dict[str, str]]:
        key = self._recent_key(conversation_id)
        rows = self.client.lrange(key, -limit, -1)
        messages: list[dict[str, str]] = []
        for row in rows:
            try:
                data = json.loads(row)
            except json.JSONDecodeError:
                continue
            messages.append(
                {
                    "role": str(data.get("role", "")),
                    "content": str(data.get("content", "")),
                }
            )
        return messages

    def set_sellersprite_raw(self, conversation_id: str, raw_data: str) -> None:
        self.client.setex(self._raw_key(conversation_id), self.raw_ttl_seconds, raw_data)

    def get_sellersprite_raw(self, conversation_id: str) -> str | None:
        value = self.client.get(self._raw_key(conversation_id))
        return str(value) if value is not None else None

    def _recent_key(self, conversation_id: str) -> str:
        return f"chat:recent:{conversation_id}"

    def _raw_key(self, conversation_id: str) -> str:
        return f"chat:raw:sellersprite:{conversation_id}"
