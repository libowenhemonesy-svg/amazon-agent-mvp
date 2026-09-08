from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.rag.rag_engine import RAGEngine
from app.routes.rag import init_rag_engine, router


class FakeVectorStore:
    def __init__(self) -> None:
        self.records = []

    def add(self, chunks, metadata) -> int:
        self.records.append((chunks, metadata))
        return len(chunks)


class OffsetVectorStore(FakeVectorStore):
    def add(self, chunks, metadata) -> int:
        super().add(chunks, metadata)
        return len(chunks) + 10


class FakeLLM:
    def invoke(self, _messages):
        return "ok"


def test_import_folder_imports_supported_files_and_skips_hidden_dirs(tmp_path: Path):
    (tmp_path / "note.md").write_text("这是主笔记内容。", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "readme.txt").write_text("这是子目录文本。", encoding="utf-8")
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / ".obsidian" / "config.md").write_text("隐藏目录不应导入。", encoding="utf-8")

    vector_store = FakeVectorStore()
    engine = RAGEngine(vector_store=vector_store, embedding_service=None, llm_client=FakeLLM())

    result = engine.import_folder(str(tmp_path))

    assert result == {"imported_files": 2, "total_chunks": 2}
    sources = [metadata[0]["source"] for _chunks, metadata in vector_store.records]
    assert sorted(sources) == ["note.md", "sub\\readme.txt"]


def test_document_indexing_preserves_upload_and_folder_count_semantics(tmp_path: Path):
    source = tmp_path / "note.md"
    source.write_text("这是知识库内容。", encoding="utf-8")
    vector_store = OffsetVectorStore()
    engine = RAGEngine(vector_store=vector_store, embedding_service=None, llm_client=FakeLLM())

    upload_result = engine.process_upload(str(source), source.name)
    folder_result = engine.import_folder(str(tmp_path))

    assert upload_result == {"filename": "note.md", "chunks": 11}
    assert folder_result == {"imported_files": 1, "total_chunks": 1}


def test_import_folder_endpoint_returns_400_for_missing_path(tmp_path: Path):
    app = FastAPI()
    app.include_router(router)
    init_rag_engine(RAGEngine(vector_store=FakeVectorStore(), embedding_service=None, llm_client=FakeLLM()))

    response = TestClient(app).post(
        "/api/rag/import-folder",
        json={"folder_path": str(tmp_path / "missing")},
    )

    assert response.status_code == 400
    assert "文件夹不存在" in response.json()["detail"]
