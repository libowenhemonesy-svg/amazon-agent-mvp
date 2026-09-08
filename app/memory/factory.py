from __future__ import annotations

from collections.abc import Mapping

from app.memory.service import MemoryService
from app.memory.short_term import InMemoryShortTermMemory, RedisShortTermMemory


def build_memory_service(*, session_factory, env: Mapping[str, str]) -> MemoryService:
    """根据环境配置构建记忆服务。"""
    redis_url = env.get("REDIS_URL", "").strip()
    short_term = InMemoryShortTermMemory()
    if redis_url:
        try:
            short_term = RedisShortTermMemory.from_url(redis_url)
        except Exception:
            short_term = InMemoryShortTermMemory()
    return MemoryService(session_factory=session_factory, short_term=short_term)
