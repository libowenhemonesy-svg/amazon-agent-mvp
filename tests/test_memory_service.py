from __future__ import annotations

from app.db.models import Base, ConversationMessage, ConversationSession, MemoryItem
from app.db.session import build_session_factory
from app.memory.service import MemoryService
from app.memory.short_term import InMemoryShortTermMemory


def make_service():
    session_factory = build_session_factory("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(session_factory.kw["bind"])
    short_term = InMemoryShortTermMemory()
    return MemoryService(session_factory=session_factory, short_term=short_term), session_factory


def test_records_conversation_messages_and_session():
    service, session_factory = make_service()

    service.record_user_message("conv-1", "查一下 SKU-001 最近7天销量")
    service.record_assistant_message("conv-1", "SKU-001 最近7天销量为 20 单")

    with session_factory() as session:
        chat_session = session.query(ConversationSession).filter_by(id="conv-1").one()
        messages = (
            session.query(ConversationMessage)
            .filter_by(session_id="conv-1")
            .order_by(ConversationMessage.id)
            .all()
        )

    assert chat_session.id == "conv-1"
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[0].content == "查一下 SKU-001 最近7天销量"
    assert messages[1].content == "SKU-001 最近7天销量为 20 单"


def test_extracts_only_explicit_user_memory():
    service, session_factory = make_service()

    service.record_user_message("conv-1", "记住：以后分析便携风扇默认看美国站，目标毛利率 35%")
    service.record_user_message("conv-1", "今天天气不错")

    with session_factory() as session:
        memories = session.query(MemoryItem).all()

    assert len(memories) == 1
    assert memories[0].scope == "user"
    assert memories[0].entity_type == "user"
    assert memories[0].entity_id == "default"
    assert memories[0].memory_type == "preference"
    assert "便携风扇默认看美国站" in memories[0].content
    assert memories[0].source == "user_explicit"
    assert memories[0].vector_status == "pending"


def test_builds_context_from_recent_messages_and_long_term_memories():
    service, _ = make_service()

    service.record_user_message("conv-1", "记住：以后分析便携风扇默认看美国站")
    service.record_assistant_message("conv-1", "已记住")

    context = service.build_context("conv-1")

    assert "【长期记忆】" in context
    assert "便携风扇默认看美国站" in context
    assert "【最近对话】" in context
    assert "用户：记住：以后分析便携风扇默认看美国站" in context
    assert "助手：已记住" in context


def test_short_term_sellersprite_raw_data_roundtrip():
    service, _ = make_service()

    service.set_sellersprite_raw("conv-1", "raw-json")

    assert service.get_sellersprite_raw("conv-1") == "raw-json"
