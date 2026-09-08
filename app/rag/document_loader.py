"""RAG 文档加载器。"""
import logging
from pathlib import Path

from pypdf import PdfReader

logger = logging.getLogger(__name__)


def load_document(file_path: str) -> str:
    """读取 PDF、TXT 或 Markdown 文档内容。"""
    path = Path(file_path)
    suffix = path.suffix.lower()

    logger.info("开始解析文档: %s", file_path)

    if suffix not in {".pdf", ".txt", ".md"}:
        logger.warning("不支持的文件类型: %s", suffix)
        raise ValueError(f"不支持的文件类型: {suffix}。支持: pdf, txt, md")

    try:
        if suffix == ".pdf":
            logger.info("使用 pypdf 解析 PDF: %s", file_path)
            reader = PdfReader(str(path))
            pages = []
            for page_index, page in enumerate(reader.pages):
                logger.debug("解析 PDF 第 %s 页: %s", page_index + 1, file_path)
                pages.append(page.extract_text() or "")
            text = "\n".join(pages)
        else:
            logger.info("读取文本文件: %s", file_path)
            text = path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.exception("文档解析失败: %s", file_path)
        raise RuntimeError(f"文档解析失败: {file_path}") from exc

    logger.info("文档解析完成: %s，字符数: %s", file_path, len(text))
    return text
