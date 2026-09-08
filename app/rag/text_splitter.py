"""RAG 文本切块工具。"""


def split_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> list[str]:
    """按固定字符数切块，并保留相邻块重叠内容。"""
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap 不能小于 0")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap 必须小于 chunk_size")

    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    step = chunk_size - chunk_overlap
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start += step

    return chunks
