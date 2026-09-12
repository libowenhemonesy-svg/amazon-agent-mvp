"""RAG 核心编排。"""
import logging
from pathlib import Path

from app.rag.config import CHUNK_OVERLAP, CHUNK_SIZE, RETRIEVE_TOP_K
from app.rag.document_loader import load_document
from app.rag.retriever import Retriever
from app.rag.text_splitter import split_text

logger = logging.getLogger(__name__)

NO_DOCUMENTS_MESSAGE = "请先上传文档到知识库。"
NO_ENOUGH_INFO_MESSAGE = "知识库中没有找到足够信息。"
MIN_RELEVANCE_SCORE = 0.2

SYSTEM_PROMPT_TEMPLATE = """你是一个知识库问答助手。
请只根据下面提供的资料回答用户问题。
如果资料中没有答案，请回答："知识库中没有找到足够信息。"
不要编造，不要使用资料外的信息。

资料：
{context}

用户问题：
{question}
"""


class RAGEngine:
    """知识库 RAG 问答引擎。"""

    def __init__(self, vector_store, embedding_service, llm_client) -> None:
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.llm_client = llm_client
        self.retriever = Retriever(vector_store)

    def process_upload(self, file_path: str, filename: str) -> dict:
        """解析文档、切块并写入向量库。"""
        logger.info("开始处理 RAG 上传文件: %s", filename)
        added, _chunk_count = self._index_document(file_path, source=filename)
        logger.info("RAG 上传处理完成: %s，chunks=%s", filename, added)
        return {"filename": filename, "chunks": added}

    def process_text(self, text: str, *, source: str, file_type: str = "web") -> dict:
        """将已验证的文本直接写入现有 RAG 索引。"""
        chunks = split_text(text, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        if not chunks:
            raise ValueError("没有可索引的文本内容")
        metadata = [{"source": source, "chunk_index": index, "file_type": file_type} for index, _ in enumerate(chunks)]
        return {"source": source, "chunks": self.vector_store.add(chunks, metadata)}

    def import_folder(self, folder_path: str) -> dict:
        """批量导入文件夹下的 Markdown、文本和 PDF 文档。"""
        folder = Path(folder_path)
        if not folder.is_dir():
            raise ValueError(f"文件夹不存在: {folder_path}")

        imported_files = 0
        total_chunks = 0
        for ext in [".md", ".txt", ".pdf"]:
            for file_path in folder.rglob(f"*{ext}"):
                relative_path = file_path.relative_to(folder)
                if any(part.startswith(".") for part in relative_path.parts):
                    continue

                try:
                    _added, chunk_count = self._index_document(
                        str(file_path),
                        source=str(relative_path),
                    )
                    imported_files += 1
                    total_chunks += chunk_count
                except Exception:
                    logger.exception("导入失败: %s", file_path)

        return {"imported_files": imported_files, "total_chunks": total_chunks}

    def _index_document(self, file_path: str, *, source: str) -> tuple[int, int]:
        """读取并切分文档，再写入向量库。"""
        text = load_document(file_path)
        chunks = split_text(text, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        file_type = Path(source).suffix.lower().lstrip(".")
        metadata = [
            {
                "source": source,
                "chunk_index": index,
                "file_type": file_type,
            }
            for index, _chunk in enumerate(chunks)
        ]
        added = self.vector_store.add(chunks, metadata)
        return added, len(chunks)

    def answer_question(self, question: str) -> dict:
        """检索知识库并调用 LLM 回答问题。"""
        if self.vector_store.count() == 0:
            return {"answer": NO_DOCUMENTS_MESSAGE, "sources": []}

        sources = self.retriever.retrieve(question, top_k=RETRIEVE_TOP_K)
        if not sources or self._is_low_relevance(sources):
            return {"answer": NO_ENOUGH_INFO_MESSAGE, "sources": self._format_sources(sources)}

        context = self._build_context(sources)
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(context=context, question=question)

        try:
            response = self.llm_client.generate(
                system_prompt=system_prompt,
                user_prompt=question,
            )
        except Exception as exc:
            logger.exception("LLM 调用失败")
            raise RuntimeError(f"LLM 调用失败: {exc}") from exc

        return {"answer": str(response), "sources": self._format_sources(sources)}

    def _is_low_relevance(self, sources: list[dict]) -> bool:
        scores = [float(source.get("score", 0.0)) for source in sources]
        return bool(scores) and max(scores) < MIN_RELEVANCE_SCORE

    def _build_context(self, sources: list[dict]) -> str:
        parts = []
        for index, source in enumerate(sources, start=1):
            parts.append(
                "\n".join(
                    [
                        f"[资料 {index}]",
                        f"来源: {source.get('source', '')}",
                        f"片段: {source.get('chunk_index', 0)}",
                        str(source.get("content", "")),
                    ]
                )
            )
        return "\n\n".join(parts)

    def _format_sources(self, sources: list[dict]) -> list[dict]:
        formatted = []
        for source in sources:
            formatted.append(
                {
                    "source": str(source.get("source", "")),
                    "chunk_index": int(source.get("chunk_index", 0)),
                    "file_type": str(source.get("file_type", "")),
                }
            )
        return formatted
