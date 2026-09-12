"""接收 Chrome 扩展采集的 Amazon 商品页面快照。"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ChromeProductCapture
from app.deps import get_session

router = APIRouter(prefix="/api/chrome", tags=["Chrome 商品采集"])


def _number(value: str) -> float | None:
    match = re.search(r"\d+(?:[,.]\d+)?", value.replace(",", ""))
    return float(match.group()) if match else None


class ProductCaptureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asin: str = Field(min_length=1, max_length=20)
    title: str = Field(default="", max_length=500)
    price: str = Field(default="", max_length=64)
    rating: str = Field(default="", max_length=64)
    review_count: str = Field(default="", max_length=64)
    bullets: list[str] = Field(default_factory=list, max_length=20)
    reviews: list[dict] = Field(default_factory=list, max_length=50)
    image: str = Field(default="", max_length=1024)
    url: str = Field(min_length=1, max_length=1024)

    @field_validator("asin")
    @classmethod
    def valid_asin(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9]{10}", cleaned):
            raise ValueError("ASIN 必须是 10 位字母或数字")
        return cleaned

    @field_validator("url")
    @classmethod
    def amazon_url(cls, value: str) -> str:
        parsed = urlparse(value.strip())
        host = parsed.hostname or ""
        if parsed.scheme != "https" or not re.fullmatch(r"(?:[a-z0-9-]+\.)?amazon\.[a-z.]+", host):
            raise ValueError("url 必须是 https Amazon 商品页链接")
        return value.strip()


def _marketplace(url: str) -> str:
    host = urlparse(url).hostname or ""
    suffix = host.rsplit("amazon.", 1)[-1].upper()
    return {"COM": "US", "CO.UK": "UK", "DE": "DE", "CO.JP": "JP"}.get(suffix, suffix)


def _serialize(row: ChromeProductCapture) -> dict:
    return {
        "id": row.id,
        "asin": row.asin,
        "title": row.title,
        "marketplace": row.marketplace,
        "price": row.price,
        "rating": row.rating,
        "review_count": row.review_count,
        "url": row.url,
        "image_url": row.image_url,
        "bullets": row.bullets,
        "reviews": row.reviews,
        "captured_at": row.captured_at.isoformat(),
    }


@router.post("/submit", status_code=201)
@router.post("/products", status_code=201)
def submit_product(payload: ProductCaptureRequest, session: Session = Depends(get_session)) -> dict:
    row = ChromeProductCapture(
        asin=payload.asin,
        title=payload.title.strip(),
        marketplace=_marketplace(payload.url),
        price=_number(payload.price),
        rating=_number(payload.rating),
        review_count=int(_number(payload.review_count) or 0) or None,
        url=payload.url,
        image_url=payload.image.strip(),
        bullets=[item.strip() for item in payload.bullets if item.strip()],
        reviews=payload.reviews,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"success": True, "product": _serialize(row)}


@router.get("/products")
def list_products(limit: int = 30, session: Session = Depends(get_session)) -> dict:
    if not 1 <= limit <= 100:
        raise HTTPException(status_code=422, detail="limit 必须在 1 到 100 之间")
    rows = session.scalars(
        select(ChromeProductCapture)
        .order_by(ChromeProductCapture.captured_at.desc(), ChromeProductCapture.id.desc())
        .limit(limit)
    ).all()
    return {"products": [_serialize(row) for row in rows]}
