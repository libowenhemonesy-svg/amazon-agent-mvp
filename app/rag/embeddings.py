"""sentence-transformers 本地向量化服务。"""
import logging
from typing import ClassVar

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingService:
    """封装 sentence-transformers 模型加载与文本向量化。"""

    _models: ClassVar[dict[str, SentenceTransformer]] = {}

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.model = self._load_model(model_name)

    @classmethod
    def _load_model(cls, model_name: str) -> SentenceTransformer:
        if model_name in cls._models:
            return cls._models[model_name]

        try:
            logger.info("加载 embedding 模型: %s", model_name)
            model = SentenceTransformer(model_name)
        except Exception as exc:
            logger.exception("embedding 模型加载失败: %s", model_name)
            raise RuntimeError(f"embedding 模型加载失败: {model_name}") from exc

        cls._models[model_name] = model
        return model

    def encode(self, texts: list[str]) -> list[list[float]]:
        """将文本列表转换为 float 向量列表。"""
        if not texts:
            return []

        embeddings = self.model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return embeddings.astype(float).tolist()

    def dimension(self) -> int:
        """返回当前 embedding 模型的向量维度。"""
        if hasattr(self.model, "get_embedding_dimension"):
            dimension = self.model.get_embedding_dimension()
        else:
            dimension = self.model.get_sentence_embedding_dimension()
        if dimension is None:
            raise RuntimeError(f"无法获取 embedding 维度: {self.model_name}")
        return int(dimension)
