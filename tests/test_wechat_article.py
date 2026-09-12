import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.importers.wechat_article import article_to_markdown, is_wechat_article_url, parse_wechat_article
from app.rag.rag_engine import RAGEngine
from app.routes import rag


PAGE = """<h1 id=\"activity-name\">运营笔记 &amp; 复盘</h1><a id=\"js_name\">测试公众号</a><div id=\"js_content\"><p>第一段内容用于测试文章导入功能。它必须足够长，才能被系统识别为可检索正文。</p><p>第二段内容说明文章会被转换为 Markdown，再由现有 RAG 管道完成切块和索引。</p></div>"""


def test_wechat_url_requires_exact_public_article_host():
    assert is_wechat_article_url("https://mp.weixin.qq.com/s/example")
    assert not is_wechat_article_url("https://example.com/s/example")
    assert not is_wechat_article_url("http://mp.weixin.qq.com/s/example")


def test_parse_article_preserves_title_author_content_and_source():
    article = parse_wechat_article(PAGE, "https://mp.weixin.qq.com/s/example")
    assert article.title == "运营笔记 & 复盘"
    assert article.author == "测试公众号"
    markdown = article_to_markdown(article)
    assert "来源：https://mp.weixin.qq.com/s/example" in markdown
    assert "第二段内容" in markdown


def test_parse_article_rejects_missing_or_short_content():
    with pytest.raises(ValueError, match="未找到"):
        parse_wechat_article("<h1 id='activity-name'>标题</h1><div id='js_content'>太短</div>", "https://mp.weixin.qq.com/s/example")


def test_import_wechat_route_uses_existing_rag_pipeline(monkeypatch):
    class VectorStore:
        def add(self, chunks, metadata):
            self.chunks, self.metadata = chunks, metadata
            return len(chunks)

    store = VectorStore()
    engine = RAGEngine(vector_store=store, embedding_service=None, llm_client=None)
    app = FastAPI()
    app.include_router(rag.router)
    rag.init_rag_engine(engine)
    monkeypatch.setattr(rag, "fetch_wechat_article", lambda _url: parse_wechat_article(PAGE, "https://mp.weixin.qq.com/s/example"))
    response = TestClient(app).post("/api/rag/import-wechat", json={"url": "https://mp.weixin.qq.com/s/example"})
    assert response.status_code == 200
    assert response.json()["chunks"] == len(store.chunks)
    assert store.metadata[0]["file_type"] == "wechat"
    assert store.metadata[0]["source"] == "https://mp.weixin.qq.com/s/example"
