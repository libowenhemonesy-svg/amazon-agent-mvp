"""系统设置路由"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from app.integrations.eccang.client import EccangClient

router = APIRouter(prefix="/api/settings", tags=["系统设置"])


class EccangSettings(BaseModel):
    app_key: str
    app_secret: str
    base_url: str = "https://open.eccang.com"


class AmazonSettings(BaseModel):
    seller_id: str
    marketplace: str = "US"
    refresh_token: str
    client_id: str = ""
    client_secret: str = ""


@router.get("")
def get_settings() -> dict:
    """获取当前设置（脱敏）"""
    return {
        "eccang": {
            "app_key": os.getenv("ECCANG_APP_KEY", ""),
            "app_secret": "***" if os.getenv("ECCANG_APP_SECRET") else "",
            "base_url": os.getenv("ECCANG_BASE_URL", "https://open.eccang.com"),
            "connected": bool(os.getenv("ECCANG_APP_KEY")),
        },
        "amazon": {
            "seller_id": os.getenv("AMAZON_SELLER_ID", ""),
            "marketplace": os.getenv("AMAZON_MARKETPLACE", "US"),
            "refresh_token": "***" if os.getenv("AMAZON_REFRESH_TOKEN") else "",
            "connected": bool(os.getenv("AMAZON_SELLER_ID")),
        },
    }


@router.post("/eccang")
def save_eccang_settings(settings: EccangSettings) -> dict:
    """保存易仓设置"""
    _update_env_file({
        "ECCANG_APP_KEY": settings.app_key,
        "ECCANG_APP_SECRET": settings.app_secret,
        "ECCANG_BASE_URL": settings.base_url,
    })
    return {"success": True, "message": "易仓设置已保存"}


@router.post("/amazon")
def save_amazon_settings(settings: AmazonSettings) -> dict:
    """保存亚马逊设置"""
    _update_env_file({
        "AMAZON_SELLER_ID": settings.seller_id,
        "AMAZON_MARKETPLACE": settings.marketplace,
        "AMAZON_REFRESH_TOKEN": settings.refresh_token,
        "AMAZON_CLIENT_ID": settings.client_id,
        "AMAZON_CLIENT_SECRET": settings.client_secret,
    })
    return {"success": True, "message": "亚马逊设置已保存"}


@router.post("/eccang/test")
def test_eccang_connection() -> dict:
    """测试易仓连接"""
    app_key = os.getenv("ECCANG_APP_KEY", "")
    app_secret = os.getenv("ECCANG_APP_SECRET", "")
    base_url = os.getenv("ECCANG_BASE_URL", "https://open.eccang.com")

    if not app_key or not app_secret:
        return {"success": False, "message": "请先配置易仓API凭证"}

    client = EccangClient(
        app_key=app_key,
        app_secret=app_secret,
        base_url=base_url,
    )
    result = client.test_connection()
    client.close()
    return result


def _update_env_file(updates: dict[str, str]) -> None:
    """更新 .env 文件"""
    env_path = Path.cwd() / ".env"
    lines = []
    existing_keys = set()

    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key = line.split("=", 1)[0]
                    if key in updates:
                        lines.append(f"{key}={updates[key]}")
                        existing_keys.add(key)
                    else:
                        lines.append(line)
                else:
                    lines.append(line)

    for key, value in updates.items():
        if key not in existing_keys:
            lines.append(f"{key}={value}")

    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    for key, value in updates.items():
        os.environ[key] = value
