from __future__ import annotations

import json
import re
from typing import Any


class ProductListingAgent:
    """Listing 文案生成 Agent：根据关键词和选品研究上下文生成 Amazon Listing 文案。"""

    def __init__(self, *, llm_client=None) -> None:
        self.llm_client = llm_client

    def run(self, state: dict[str, Any], *, research_context: dict[str, Any] | None = None) -> dict[str, Any]:
        entities = state.get("entities", {})
        research_context = research_context or {}
        keyword = (entities.get("keyword") or research_context.get("keyword") or "").strip()
        if not keyword:
            return {
                "agent_name": "ProductListingAgent",
                "summary": "请先提供关键词或先做选品研究，再让我根据关键词生成 Listing 文案。",
                "keyword": "",
                "listing": {},
            }

        if self.llm_client is None:
            return {
                "agent_name": "ProductListingAgent",
                "summary": "未配置真实 LLM，无法生成 Listing 文案。请配置 DEEPSEEK_API_KEY 后重试。",
                "keyword": keyword,
                "listing": {},
            }

        raw_text = self._generate_raw_listing(keyword, research_context)
        listing = _parse_listing(raw_text)
        if not listing["title"]:
            return {
                "agent_name": "ProductListingAgent",
                "summary": "真实 LLM 没有返回可解析的 Listing 文案，请重试或检查模型输出。",
                "keyword": keyword,
                "listing": {},
                "raw": raw_text,
            }

        return {
            "agent_name": "ProductListingAgent",
            "summary": _format_listing_summary(keyword, listing),
            "keyword": keyword,
            "listing": listing,
            "raw": raw_text,
        }

    def _generate_raw_listing(self, keyword: str, research_context: dict[str, Any]) -> str:
        return self.llm_client.generate(
            _system_prompt(),
            _user_prompt(keyword, research_context),
        )


def _system_prompt() -> str:
    return (
        "You are ProductListingAgent, an Amazon US listing copywriting specialist. "
        "Generate compliant, conversion-focused listing copy from the provided product research context. "
        "Avoid trademarked brands, medical claims, exaggerated guarantees, and text that cannot be supported. "
        "Return only valid JSON with exactly these keys: title, bullet_points, description, search_terms. "
        "bullet_points must be an array of exactly five strings."
    )


def _user_prompt(keyword: str, research_context: dict[str, Any]) -> str:
    product_context = research_context.get("product_context") or ""
    decision = research_context.get("decision") or (research_context.get("raw") or {}).get("decision") or {}
    competitors = research_context.get("competitors") or []
    pricing = research_context.get("pricing") or {}
    return (
        f"Keyword: {keyword}\n"
        f"Product information: {product_context}\n"
        f"Market decision: {decision}\n"
        f"Pricing context: {pricing}\n"
        f"Competitor samples: {competitors[:5]}\n\n"
        "Create:\n"
        "- One Amazon title under 180 characters.\n"
        "- Five bullet points focused on benefits and concrete features.\n"
        "- One product description paragraph.\n"
        "- Backend search terms as a single deduplicated phrase list under 250 bytes."
    )


def _parse_listing(text: str) -> dict[str, Any]:
    json_listing = _parse_json_listing(text)
    if json_listing is not None:
        return json_listing
    title = _extract_single_line(text, "Title")
    description = _extract_single_line(text, "Description")
    search_terms = _extract_single_line(text, "Search Terms")
    bullets = _extract_bullets(text)
    return {
        "title": title,
        "bullet_points": bullets[:5],
        "description": description,
        "search_terms": search_terms,
    }


def _parse_json_listing(text: str) -> dict[str, Any] | None:
    payload_text = text.strip()
    if payload_text.startswith("```"):
        payload_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", payload_text, flags=re.IGNORECASE)
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    bullets = payload.get("bullet_points")
    return {
        "title": str(payload.get("title") or "").strip(),
        "bullet_points": [str(item).strip() for item in bullets if str(item).strip()]
        if isinstance(bullets, list)
        else [],
        "description": str(payload.get("description") or "").strip(),
        "search_terms": str(payload.get("search_terms") or "").strip(),
    }


def _extract_single_line(text: str, label: str) -> str:
    pattern = rf"^\s*(?:\*\*)?{re.escape(label)}\s*:(?:\*\*)?\s*(.+)$"
    match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else ""


def _extract_bullets(text: str) -> list[str]:
    marker = re.search(
        r"^\s*(?:\*\*)?Bullet Points\s*:(?:\*\*)?\s*$",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if not marker:
        return []
    rest = text[marker.end():]
    next_section = re.search(
        r"^\s*(?:\*\*)?(?:Description|Search Terms)\s*:(?:\*\*)?",
        rest,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    bullet_block = rest[: next_section.start()] if next_section else rest
    bullets = []
    for line in bullet_block.splitlines():
        cleaned = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
        if cleaned:
            bullets.append(cleaned)
    return bullets


def _format_listing_summary(keyword: str, listing: dict[str, Any]) -> str:
    bullets = "\n".join(f"- {item}" for item in listing["bullet_points"])
    return (
        f"已根据关键词 {keyword} 生成 Amazon Listing 文案。\n\n"
        f"Title:\n{listing['title']}\n\n"
        f"Bullet Points:\n{bullets}\n\n"
        f"Description:\n{listing['description']}\n\n"
        f"Search Terms:\n{listing['search_terms']}"
    )
