from app.memory.factory import build_memory_service
from app.memory.service import MemoryService
from app.memory.short_term import InMemoryShortTermMemory, RedisShortTermMemory


def test_build_memory_service_uses_in_memory_short_term_without_redis_url():
    service = build_memory_service(session_factory=None, env={})

    assert isinstance(service, MemoryService)
    assert isinstance(service.short_term, InMemoryShortTermMemory)


def test_build_memory_service_uses_redis_when_url_is_configured(monkeypatch):
    created = {}

    def fake_from_url(redis_url):
        created["redis_url"] = redis_url
        return InMemoryShortTermMemory()

    monkeypatch.setattr(RedisShortTermMemory, "from_url", fake_from_url)

    service = build_memory_service(
        session_factory=None,
        env={"REDIS_URL": "redis://localhost:6379/0"},
    )

    assert isinstance(service, MemoryService)
    assert created["redis_url"] == "redis://localhost:6379/0"
