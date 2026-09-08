"""RAG 知识库问答路由。"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.rag.config import ALLOWED_EXTENSIONS, UPLOAD_DIR

if TYPE_CHECKING:
    from app.rag.rag_engine import RAGEngine

router = APIRouter(prefix="/api/rag", tags=["RAG"])

_rag_engine: "RAGEngine | None" = None


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


class ImportFolderRequest(BaseModel):
    folder_path: str = Field(..., min_length=1)


class Source(BaseModel):
    source: str
    chunk_index: int
    file_type: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]


def init_rag_engine(engine) -> None:
    """由 main.py 注入 RAG 引擎。"""
    global _rag_engine
    _rag_engine = engine


def get_rag_engine():
    if _rag_engine is None:
        raise HTTPException(status_code=503, detail="RAG 引擎未初始化")
    return _rag_engine


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.post("/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="不支持的文件类型")

    upload_dir = Path(UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(file.filename or "upload").name
    file_path = upload_dir / filename

    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        result = get_rag_engine().process_upload(str(file_path), filename)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        await file.close()

    return {**result, "message": "upload success"}


@router.post("/import-folder")
async def import_folder(request: ImportFolderRequest) -> dict:
    try:
        result = get_rag_engine().import_folder(request.folder_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {**result, "message": "import complete"}


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        result = get_rag_engine().answer_question(request.question)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ChatResponse(**result)
