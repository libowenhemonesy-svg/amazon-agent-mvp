"""AI 聊天路由"""
from __future__ import annotations

import json
from fastapi import APIRouter, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(tags=["AI 聊天"])


class ChatRequest(BaseModel):
    message: str
    conversation_id: str = "default"


# 由 main.py 注入
_chat_graph = None
_memory_service = None


def init_chat_graph(chat_graph):
    """初始化聊天图"""
    global _chat_graph
    _chat_graph = chat_graph


def init_chat_memory_service(memory_service):
    """初始化聊天记忆服务。"""
    global _memory_service
    _memory_service = memory_service


@router.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """聊天端点 - SSE 流式响应"""
    if _chat_graph is None:
        return {"error": "Chat graph not initialized"}

    async def event_stream():
        try:
            async for event in _chat_graph.chat_stream(req.message, req.conversation_id):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/chat/history")
def get_chat_history(conversation_id: str = "default") -> dict:
    """获取当前会话聊天历史。"""
    if _memory_service is None:
        return {"conversation_id": conversation_id, "messages": []}
    return {
        "conversation_id": conversation_id,
        "messages": _memory_service.list_conversation_messages(conversation_id),
    }


@router.get("/chat/sessions")
def get_chat_sessions() -> dict:
    """获取聊天会话列表。"""
    if _memory_service is None:
        return {"sessions": []}
    return {"sessions": _memory_service.list_conversation_sessions()}
