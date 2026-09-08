from __future__ import annotations

import base64
import os
import uuid
from pathlib import Path
from typing import Any, Mapping

import httpx


DEFAULT_ARK_IMAGE_MODEL = ""
DEFAULT_ARK_IMAGE_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_ARK_IMAGE_SIZE = "1024x1024"
DEFAULT_BAILIAN_IMAGE_MODEL = "qwen-image-2.0-pro"
DEFAULT_BAILIAN_IMAGE_BASE_URL = "https://dashscope.aliyuncs.com/api/v1"
DEFAULT_BAILIAN_IMAGE_SIZE = "1024x1024"


class DoubaoArkImageClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_ARK_IMAGE_MODEL,
        base_url: str = DEFAULT_ARK_IMAGE_BASE_URL,
        size: str = DEFAULT_ARK_IMAGE_SIZE,
        timeout_seconds: float = 60,
        http_client=None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.size = size
        self.timeout_seconds = timeout_seconds
        self.http_client = http_client or httpx

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "DoubaoArkImageClient | None":
        env = os.environ if env is None else env
        api_key = (env.get("ARK_API_KEY") or "").strip()
        model = (env.get("ARK_IMAGE_MODEL") or DEFAULT_ARK_IMAGE_MODEL).strip()
        if not api_key or not model:
            return None
        return cls(
            api_key=api_key,
            model=model,
            base_url=env.get("ARK_IMAGE_BASE_URL", DEFAULT_ARK_IMAGE_BASE_URL),
            size=env.get("ARK_IMAGE_SIZE", DEFAULT_ARK_IMAGE_SIZE),
            timeout_seconds=float(env.get("ARK_IMAGE_TIMEOUT_SECONDS", "60")),
        )

    def generate_image(self, prompt: str) -> bytes:
        response = self.http_client.post(
            f"{self.base_url}/images/generations",
            json={
                "model": self.model,
                "prompt": prompt,
                "size": self.size,
                "response_format": "b64_json",
            },
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        try:
            image_payload = payload["data"][0]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Ark image response missing data: {payload}") from exc

        if image_payload.get("b64_json"):
            return base64.b64decode(image_payload["b64_json"])
        if image_payload.get("url"):
            image_response = self.http_client.get(image_payload["url"], timeout=self.timeout_seconds)
            image_response.raise_for_status()
            return image_response.content
        raise RuntimeError(f"Ark image response missing image content: {payload}")


class BailianImageClient(DoubaoArkImageClient):
    """阿里百炼 / 千问图片生成客户端，使用 OpenAI 兼容 images API。"""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_BAILIAN_IMAGE_MODEL,
        base_url: str = DEFAULT_BAILIAN_IMAGE_BASE_URL,
        size: str = DEFAULT_BAILIAN_IMAGE_SIZE,
        timeout_seconds: float = 60,
        http_client=None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url,
            size=size,
            timeout_seconds=timeout_seconds,
            http_client=http_client,
        )

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "BailianImageClient | None":
        env = os.environ if env is None else env
        api_key = (env.get("BAILIAN_API_KEY") or env.get("DASHSCOPE_API_KEY") or "").strip()
        if not api_key:
            return None
        return cls(
            api_key=api_key,
            model=(env.get("BAILIAN_IMAGE_MODEL") or DEFAULT_BAILIAN_IMAGE_MODEL).strip(),
            base_url=env.get("BAILIAN_IMAGE_BASE_URL", DEFAULT_BAILIAN_IMAGE_BASE_URL),
            size=env.get("BAILIAN_IMAGE_SIZE", DEFAULT_BAILIAN_IMAGE_SIZE),
            timeout_seconds=float(env.get("BAILIAN_IMAGE_TIMEOUT_SECONDS", "60")),
        )

    def generate_image(self, prompt: str) -> bytes:
        response = self.http_client.post(
            f"{self.base_url}/services/aigc/multimodal-generation/generation",
            json={
                "model": self.model,
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": [{"text": prompt}],
                        }
                    ],
                },
                "parameters": {
                    "size": _dashscope_size(self.size),
                    "watermark": False,
                },
            },
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        image_url = _extract_dashscope_image_url(payload)
        image_response = self.http_client.get(image_url, timeout=self.timeout_seconds)
        image_response.raise_for_status()
        return image_response.content


class ProductImageAgent:
    """产品图生成 Agent：根据选品关键词生成产品图 prompt 并调用图片模型生图。"""

    def __init__(
        self,
        *,
        output_dir: str | Path,
        image_client: DoubaoArkImageClient | None = None,
        ark_client: DoubaoArkImageClient | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.image_client = image_client or ark_client

    def run(self, state: dict, *, research_context: dict[str, Any] | None = None) -> dict:
        entities = state.get("entities", {})
        research_context = research_context or {}
        keyword = (entities.get("keyword") or research_context.get("keyword") or "").strip()
        if not keyword:
            return {
                "agent_name": "ProductImageAgent",
                "summary": "请先提供关键词或先做选品研究，再让我根据关键词生成产品图。",
                "keyword": "",
                "prompt": "",
                "image_url": "",
                "image_type": "",
            }

        image_type = _detect_image_type(state.get("user_message", ""))
        prompt = self._build_prompt(keyword=keyword, image_type=image_type, research_context=research_context)
        if self.image_client is None:
            return {
                "agent_name": "ProductImageAgent",
                "summary": "已生成产品图提示词，但未配置 BAILIAN_API_KEY，暂未调用阿里百炼/千问图片模型生图。",
                "keyword": keyword,
                "prompt": prompt,
                "image_url": "",
                "image_type": image_type,
            }

        try:
            image_bytes = self.image_client.generate_image(prompt)
            image_url = self._save_image(image_bytes)
        except Exception as exc:
            return {
                "agent_name": "ProductImageAgent",
                "summary": f"阿里百炼/千问图片模型生图失败，已保留可重试的产品图提示词：{exc}",
                "keyword": keyword,
                "prompt": prompt,
                "image_url": "",
                "image_type": image_type,
            }

        return {
            "agent_name": "ProductImageAgent",
            "summary": f"已根据关键词 {keyword} 生成产品图。",
            "keyword": keyword,
            "prompt": prompt,
            "image_url": image_url,
            "image_type": image_type,
        }

    def _build_prompt(self, *, keyword: str, image_type: str, research_context: dict[str, Any]) -> str:
        decision = (research_context.get("raw") or {}).get("decision") or research_context.get("decision") or {}
        decision_label = decision.get("label", "")
        listing = research_context.get("listing") or {}
        listing_title = listing.get("title", "")
        listing_bullets = listing.get("bullet_points") or []
        listing_note = _format_listing_visual_note(listing_title, listing_bullets)
        image_direction = (
            "clean Amazon main image on pure white background, product centered, no props"
            if image_type == "main_image"
            else "premium lifestyle scene showing the product in realistic daily use"
        )
        market_note = f"Market decision context: {decision_label}." if decision_label else ""
        return (
            f"Create a high-converting Amazon US product image for keyword: {keyword}. "
            f"Image type: {image_type}. Direction: {image_direction}. "
            "Commercial product photography, sharp focus, realistic materials, natural lighting, "
            "clear product silhouette, no logos, no trademarked brands, no misleading claims, "
            "no text rendered inside the image. "
            f"{listing_note} "
            f"{market_note}"
        ).strip()

    def _save_image(self, image_bytes: bytes) -> str:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid.uuid4().hex}.png"
        (self.output_dir / filename).write_bytes(image_bytes)
        return f"/static/generated/{filename}"


def _detect_image_type(message: str) -> str:
    text = message.lower()
    if "主图" in text or "main image" in text or "white background" in text or "白底" in text:
        return "main_image"
    return "lifestyle_image"


def _format_listing_visual_note(title: str, bullets: list[str]) -> str:
    parts = []
    if title:
        parts.append(f"Listing title to align with: {title}.")
    if bullets:
        parts.append("Visual benefits to communicate: " + "; ".join(str(item) for item in bullets[:5]) + ".")
    return " ".join(parts)


def _dashscope_size(size: str) -> str:
    return size.replace("x", "*").replace("X", "*")


def _extract_dashscope_image_url(payload: dict[str, Any]) -> str:
    try:
        content = payload["output"]["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"DashScope image response missing content: {payload}") from exc

    if not isinstance(content, list):
        raise RuntimeError(f"DashScope image response content is not a list: {payload}")
    for item in content:
        if isinstance(item, dict) and item.get("image"):
            return str(item["image"])
    raise RuntimeError(f"DashScope image response missing image url: {payload}")
