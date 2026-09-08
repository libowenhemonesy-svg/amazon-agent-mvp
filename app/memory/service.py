from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ConversationMessage, ConversationSession, MemoryItem
from app.memory.short_term import InMemoryShortTermMemory


class MemoryVectorSink:
    """记忆向量化预留接口；第一版不写入 Qdrant。"""

    def enqueue(self, memory_item: MemoryItem) -> None:
        return None


class MemoryService:
    """统一管理长期记忆和短期上下文。"""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session] | None = None,
        short_term=None,
        vector_sink: MemoryVectorSink | None = None,
        user_id: str = "default",
    ) -> None:
        self.session_factory = session_factory
        self.short_term = short_term or InMemoryShortTermMemory()
        self.vector_sink = vector_sink or MemoryVectorSink()
        self.user_id = user_id

    def record_user_message(self, conversation_id: str, content: str) -> None:
        self._record_message(conversation_id, "user", content)
        self.short_term.append_recent_message(conversation_id, "user", content)
        self._extract_explicit_memory(content)

    def record_assistant_message(self, conversation_id: str, content: str) -> None:
        if not content.strip():
            return
        self._record_message(conversation_id, "assistant", content)
        self.short_term.append_recent_message(conversation_id, "assistant", content)

    def record_tool_message(
        self,
        conversation_id: str,
        *,
        tool_name: str,
        content: str = "",
        tool_result: dict | None = None,
    ) -> None:
        self._record_message(
            conversation_id,
            "tool",
            content,
            tool_name=tool_name,
            tool_result=tool_result,
        )

    def build_context(self, conversation_id: str, *, memory_limit: int = 8, recent_limit: int = 8) -> str:
        sections: list[str] = []
        memories = self._list_long_term_memories(limit=memory_limit)
        if memories:
            sections.append("【长期记忆】")
            sections.extend(f"- {item.content}" for item in memories)

        recent_messages = self.short_term.get_recent_messages(conversation_id, limit=recent_limit)
        if recent_messages:
            sections.append("【最近对话】")
            for message in recent_messages:
                role = _role_label(message.get("role", ""))
                content = str(message.get("content", "")).strip()
                if content:
                    sections.append(f"{role}：{content}")

        return "\n".join(sections)

    def set_sellersprite_raw(self, conversation_id: str, raw_data: str) -> None:
        self.short_term.set_sellersprite_raw(conversation_id, raw_data)

    def get_sellersprite_raw(self, conversation_id: str) -> str | None:
        return self.short_term.get_sellersprite_raw(conversation_id)

    def list_conversation_messages(self, conversation_id: str, *, limit: int = 100) -> list[dict]:
        if self.session_factory is None:
            return []
        with self.session_factory() as session:
            rows = (
                session.scalars(
                    select(ConversationMessage)
                    .where(ConversationMessage.session_id == conversation_id)
                    .order_by(ConversationMessage.id.desc())
                    .limit(limit)
                )
                .all()
            )
        messages = []
        for row in reversed(rows):
            messages.append(
                {
                    "id": row.id,
                    "role": row.role,
                    "content": row.content,
                    "tool_name": row.tool_name,
                    "created_at": row.created_at.isoformat() if row.created_at else "",
                }
            )
        return messages

    def list_conversation_sessions(self, *, limit: int = 30) -> list[dict]:
        if self.session_factory is None:
            return []
        with self.session_factory() as session:
            rows = session.execute(
                select(
                    ConversationSession,
                    func.count(ConversationMessage.id).label("message_count"),
                )
                .outerjoin(
                    ConversationMessage,
                    ConversationMessage.session_id == ConversationSession.id,
                )
                .where(ConversationSession.user_id == self.user_id)
                .group_by(ConversationSession.id)
                .order_by(ConversationSession.updated_at.desc(), ConversationSession.created_at.desc())
                .limit(limit)
            ).all()

        sessions = []
        for chat_session, message_count in rows:
            sessions.append(
                {
                    "id": chat_session.id,
                    "title": chat_session.title or chat_session.id,
                    "summary": chat_session.summary or "",
                    "message_count": int(message_count or 0),
                    "created_at": chat_session.created_at.isoformat() if chat_session.created_at else "",
                    "updated_at": chat_session.updated_at.isoformat() if chat_session.updated_at else "",
                }
            )
        return sessions

    def _record_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        *,
        tool_name: str | None = None,
        tool_result: dict | None = None,
    ) -> None:
        if self.session_factory is None:
            return
        now = datetime.now(UTC)
        with self.session_factory() as session:
            chat_session = session.get(ConversationSession, conversation_id)
            if chat_session is None:
                chat_session = ConversationSession(
                    id=conversation_id,
                    user_id=self.user_id,
                    title=_build_title(content),
                    created_at=now,
                    updated_at=now,
                )
                session.add(chat_session)
            else:
                chat_session.updated_at = now
                if not chat_session.title:
                    chat_session.title = _build_title(content)

            session.add(
                ConversationMessage(
                    session_id=conversation_id,
                    role=role,
                    content=content,
                    tool_name=tool_name,
                    tool_result=tool_result,
                    created_at=now,
                )
            )
            session.commit()

    def _extract_explicit_memory(self, content: str) -> None:
        if self.session_factory is None:
            return
        memory_text = _extract_memory_text(content)
        if not memory_text:
            return
        now = datetime.now(UTC)
        with self.session_factory() as session:
            existing = session.scalar(
                select(MemoryItem).where(
                    MemoryItem.scope == "user",
                    MemoryItem.entity_type == "user",
                    MemoryItem.entity_id == self.user_id,
                    MemoryItem.content == memory_text,
                )
            )
            if existing is not None:
                existing.updated_at = now
                session.commit()
                return

            memory_item = MemoryItem(
                scope="user",
                entity_type="user",
                entity_id=self.user_id,
                memory_type="preference",
                content=memory_text,
                source="user_explicit",
                confidence=1.0,
                vector_status="pending",
                created_at=now,
                updated_at=now,
            )
            session.add(memory_item)
            session.commit()
            session.refresh(memory_item)
            self.vector_sink.enqueue(memory_item)

    def _list_long_term_memories(self, *, limit: int) -> list[MemoryItem]:
        if self.session_factory is None:
            return []
        with self.session_factory() as session:
            return list(
                session.scalars(
                    select(MemoryItem)
                    .where(MemoryItem.scope == "user", MemoryItem.entity_id == self.user_id)
                    .order_by(MemoryItem.updated_at.desc(), MemoryItem.id.desc())
                    .limit(limit)
                ).all()
            )


def _extract_memory_text(content: str) -> str:
    text = content.strip()
    patterns = [
        r"记住\s*[:：]?\s*(.+)",
        r"以后默认\s*[:：]?\s*(.+)",
        r"我的偏好\s*[:：]?\s*(.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
    return ""


def _build_title(content: str) -> str:
    title = " ".join(content.strip().split())
    return title[:80]


def _role_label(role: str) -> str:
    if role == "user":
        return "用户"
    if role == "assistant":
        return "助手"
    if role == "tool":
        return "工具"
    return role or "消息"
