"""Qdrant 向量库管理。"""
import logging
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, Filter, FilterSelector, PointStruct, VectorParams

from app.rag.config import QDRANT_COLLECTION, QDRANT_URL
from app.rag.embeddings import EmbeddingService

logger = logging.getLogger(__name__)


class VectorStore:
    """封装 Qdrant 的写入、检索和清空操作。"""

    def __init__(self, persist_dir: str, embedding_service: EmbeddingService) -> None:
        self.persist_dir = persist_dir
        self.embedding_service = embedding_service
        self.collection_name = QDRANT_COLLECTION
        self.client = self._build_client(persist_dir)
        self._ensure_collection()

    def add(self, chunks: list[str], metadata: list[dict]) -> int:
        """向向量库添加文本块，返回添加数量。"""
        if len(chunks) != len(metadata):
            raise ValueError("chunks 和 metadata 长度必须一致")
        if not chunks:
            return 0

        embeddings = self.embedding_service.encode(chunks)
        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    **item_metadata,
                    "content": chunk,
                },
            )
            for chunk, embedding, item_metadata in zip(chunks, embeddings, metadata)
        ]

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True,
        )
        logger.info("已写入 Qdrant 文档块: %s", len(chunks))
        return len(chunks)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """检索相似文本块。"""
        if top_k <= 0:
            return []
        if self.count() == 0:
            return []

        query_embedding = self.embedding_service.encode([query])[0]
        result = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            limit=top_k,
            with_payload=True,
        )

        rows: list[dict] = []
        for point in result.points:
            payload = point.payload or {}
            rows.append(
                {
                    "content": str(payload.get("content", "")),
                    "score": float(point.score),
                    "source": str(payload.get("source", "")),
                    "chunk_index": int(payload.get("chunk_index", 0)),
                }
            )
        return rows

    def count(self) -> int:
        """返回当前 collection 的点数量。"""
        result = self.client.count(collection_name=self.collection_name, exact=True)
        return int(result.count)

    def clear(self) -> None:
        """清空向量库中的 points，保留 collection 结构。"""
        if not self.client.collection_exists(self.collection_name):
            self._create_collection()
            return

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=FilterSelector(filter=Filter(must=[])),
            wait=True,
        )
        logger.info("已清空 Qdrant collection: %s", self.collection_name)

    def _build_client(self, persist_dir: str) -> QdrantClient:
        # 内存模式（测试用）
        if persist_dir == ":memory:":
            return QdrantClient(":memory:")

        # Docker / 远程 Qdrant
        if persist_dir.startswith(("http://", "https://")):
            return QdrantClient(url=persist_dir)

        # Docker Qdrant 默认地址
        return QdrantClient(url=QDRANT_URL)

    def _ensure_collection(self) -> None:
        expected_dimension = int(self.embedding_service.dimension())

        if not self.client.collection_exists(self.collection_name):
            self._create_collection()
            return

        actual_dimension = self._get_collection_dimension()
        if actual_dimension != expected_dimension:
            logger.warning(
                "Qdrant collection 维度不匹配，重建 collection: actual=%s expected=%s",
                actual_dimension,
                expected_dimension,
            )
            self._recreate_collection()

    def _create_collection(self) -> None:
        logger.info("创建 Qdrant collection: %s", self.collection_name)
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=int(self.embedding_service.dimension()),
                distance=Distance.COSINE,
            ),
        )

    def _recreate_collection(self) -> None:
        try:
            self.client.delete_collection(self.collection_name)
        except Exception as exc:
            logger.exception("删除 Qdrant collection 失败: %s", self.collection_name)
            raise RuntimeError(f"Qdrant collection 重建失败: {self.collection_name}") from exc
        self._create_collection()

    def _get_collection_dimension(self) -> int:
        collection = self.client.get_collection(self.collection_name)
        vectors = collection.config.params.vectors

        if isinstance(vectors, dict):
            first_vector = next(iter(vectors.values()))
            return int(first_vector.size)

        return int(vectors.size)
