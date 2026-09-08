from app.db.models import Base
from app.db.session import build_session_factory
from app.memory.service import MemoryService
from app.routes.chat import (
    get_chat_history,
    get_chat_sessions,
    init_chat_graph,
    init_chat_memory_service,
)


def test_get_chat_history_returns_persisted_messages():
    session_factory = build_session_factory("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(session_factory.kw["bind"])
    memory_service = MemoryService(session_factory=session_factory)
    memory_service.record_user_message("conv-history", "你好")
    memory_service.record_assistant_message("conv-history", "你好，请问需要分析什么？")

    init_chat_memory_service(memory_service)

    result = get_chat_history("conv-history")

    assert result["conversation_id"] == "conv-history"
    assert [message["role"] for message in result["messages"]] == ["user", "assistant"]
    assert result["messages"][0]["content"] == "你好"
    assert result["messages"][1]["content"] == "你好，请问需要分析什么？"

    init_chat_graph(None)
    init_chat_memory_service(None)


def test_get_chat_sessions_returns_recent_sessions_with_message_count():
    session_factory = build_session_factory("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(session_factory.kw["bind"])
    memory_service = MemoryService(session_factory=session_factory)
    memory_service.record_user_message("conv-old", "第一段对话")
    memory_service.record_assistant_message("conv-old", "第一段回复")
    memory_service.record_user_message("conv-new", "查询广告 ACOS")

    init_chat_memory_service(memory_service)

    result = get_chat_sessions()

    assert [item["id"] for item in result["sessions"]] == ["conv-new", "conv-old"]
    assert result["sessions"][0]["title"] == "查询广告 ACOS"
    assert result["sessions"][0]["message_count"] == 1
    assert result["sessions"][1]["message_count"] == 2

    init_chat_graph(None)
    init_chat_memory_service(None)
