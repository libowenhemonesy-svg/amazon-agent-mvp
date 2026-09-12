"""微信公众号文章导入：只解析用户明确提交的公开文章链接。"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx


@dataclass(frozen=True)
class WechatArticle:
    title: str
    author: str
    content: str
    url: str


def is_wechat_article_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    return parsed.scheme == "https" and parsed.hostname == "mp.weixin.qq.com" and parsed.path.startswith("/s/")


def _strip_html(value: str) -> str:
    value = re.sub(r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>", "", value, flags=re.DOTALL | re.IGNORECASE)
    value = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</h[1-6]>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", "", value)
    return "\n".join(line.strip() for line in html.unescape(value).splitlines() if line.strip())


def parse_wechat_article(page: str, url: str) -> WechatArticle:
    title_match = re.search(r'<h1[^>]*id=["\']activity-name["\'][^>]*>(.*?)</h1>', page, re.DOTALL | re.IGNORECASE)
    content_match = re.search(r'<div[^>]*id=["\']js_content["\'][^>]*>(.*?)</div>', page, re.DOTALL | re.IGNORECASE)
    author_match = re.search(r'id=["\']js_name["\'][^>]*>(.*?)</', page, re.DOTALL | re.IGNORECASE)
    title = _strip_html(title_match.group(1)) if title_match else ""
    content = _strip_html(content_match.group(1)) if content_match else ""
    author = _strip_html(author_match.group(1)) if author_match else ""
    if not title or len(content) < 50:
        raise ValueError("未找到可导入的文章正文；文章可能已删除、受访问限制或页面结构已变更")
    return WechatArticle(title=title, author=author, content=content, url=url)


def fetch_wechat_article(url: str) -> WechatArticle:
    if not is_wechat_article_url(url):
        raise ValueError("请提供 https://mp.weixin.qq.com/s/ 开头的文章链接")
    with httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": "AmazonAgentKnowledgeImporter/1.0"}) as client:
        response = client.get(url)
    if response.status_code == 404:
        raise ValueError("文章不存在或已删除")
    if response.status_code != 200:
        raise RuntimeError(f"文章请求失败，HTTP {response.status_code}")
    return parse_wechat_article(response.text, url)


def article_to_markdown(article: WechatArticle) -> str:
    author = f"\n作者：{article.author}" if article.author else ""
    return f"# {article.title}{author}\n来源：{article.url}\n\n{article.content}\n"
