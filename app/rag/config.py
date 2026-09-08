"""RAG 模块配置 —— 所有参数可通过环境变量覆盖。"""
import os

CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "50"))
EMBEDDING_MODEL = os.getenv("RAG_EMBEDDING_MODEL", r"D:\ai_models\bge-m3")
EMBEDDING_DIM = int(os.getenv("RAG_EMBEDDING_DIM", "1024"))
VECTOR_DB_DIR = os.getenv("RAG_VECTOR_DB_DIR", "vector_db")
QDRANT_URL = os.getenv("RAG_QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("RAG_QDRANT_COLLECTION", "rag_documents")
UPLOAD_DIR = os.getenv("RAG_UPLOAD_DIR", "uploads")
RETRIEVE_TOP_K = int(os.getenv("RAG_RETRIEVE_TOP_K", "5"))
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}
