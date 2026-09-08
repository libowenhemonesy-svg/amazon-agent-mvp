"""RAG 相似度检索器。"""

from app.rag.vector_store import VectorStore


class Retriever:
    """封装向量库检索入口。"""

    def __init__(self, vector_store: VectorStore) -> None:
        self.vector_store = vector_store

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """返回与 query 相似的来源列表。"""
        return self.vector_store.search(query, top_k=top_k)
