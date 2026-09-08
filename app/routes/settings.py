"""管理员 MCP 数据源设置路由。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlsplit
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.agents.mcp_tools import StreamableHttpMCPClient
from app.auth.dependencies import get_current_admin
from app.auth.schemas import UserInfo
from app.db.models import McpDataSource
from app.deps import get_session
from app.selection.contracts import McpCapability
from app.selection.credentials import EnvCredentialStore

router = APIRouter(prefix="/api/settings", tags=["系统设置"])


class CapabilityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str = Field(min_length=1, max_length=256)
    argument_map: dict[str, str] = Field(default_factory=dict)
    field_mapping: dict[str, str] = Field(default_factory=dict)
    timeout: float | None = Field(default=None, gt=0, le=300)

    @field_validator("tool")
    @classmethod
    def normalize_tool(cls, value: str) -> str:
        tool = value.strip()
        if not tool:
            raise ValueError("工具名称不能为空")
        return tool


class McpSourceBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    url: str
    transport: Literal["streamable_http"] = "streamable_http"
    enabled: bool = True
    priority: int = Field(default=10, gt=0)
    capabilities: dict[McpCapability, CapabilityConfig]

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("数据源名称不能为空")
        return name

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(
        cls, value: dict[McpCapability, CapabilityConfig]
    ) -> dict[McpCapability, CapabilityConfig]:
        if not value:
            raise ValueError("至少配置一个 MCP 能力")
        return value


class McpSourceCreate(McpSourceBase):
    api_key: str = ""
    headers: dict[str, str] = Field(default_factory=dict)


class McpSourceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    url: str | None = None
    transport: Literal["streamable_http"] | None = None
    enabled: bool | None = None
    priority: int | None = Field(default=None, gt=0)
    capabilities: dict[McpCapability, CapabilityConfig] | None = None
    api_key: str = ""
    headers: dict[str, str] = Field(default_factory=dict)

    _normalize_name = field_validator("name")(McpSourceBase.normalize_name.__func__)

    @field_validator("capabilities")
    @classmethod
    def validate_optional_capabilities(
        cls, value: dict[McpCapability, CapabilityConfig] | None
    ) -> dict[McpCapability, CapabilityConfig] | None:
        if value is not None and not value:
            raise ValueError("至少配置一个 MCP 能力")
        return value


def get_credential_store() -> EnvCredentialStore:
    return EnvCredentialStore(os.environ, _update_env_file)


def build_mcp_client(source: McpDataSource, headers: dict[str, str]) -> StreamableHttpMCPClient:
    return StreamableHttpMCPClient(url=source.url, headers=headers)


@router.get("/mcp-sources")
def list_mcp_sources(
    _admin: UserInfo = Depends(get_current_admin),
    db: Session = Depends(get_session),
) -> dict[str, list[dict[str, Any]]]:
    sources = db.query(McpDataSource).order_by(McpDataSource.priority, McpDataSource.id).all()
    store = get_credential_store()
    return {"items": [_serialize_source(source, store) for source in sources]}


@router.post("/mcp-sources", status_code=status.HTTP_201_CREATED)
def create_mcp_source(
    payload: McpSourceCreate,
    _admin: UserInfo = Depends(get_current_admin),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    url = _validate_mcp_url(payload.url)
    _ensure_unique_name(db, payload.name)
    source = McpDataSource(
        name=payload.name,
        url=url,
        transport=payload.transport,
        enabled=payload.enabled,
        priority=payload.priority,
        capability_config_json=_serialize_capabilities(payload.capabilities),
    )
    db.add(source)
    db.flush()
    source.credential_reference = f"MCP_SOURCE_{source.id}"
    store = get_credential_store()
    store.save(
        source.credential_reference,
        api_key=payload.api_key,
        headers=payload.headers,
    )
    db.commit()
    db.refresh(source)
    return _serialize_source(source, store)


@router.patch("/mcp-sources/{source_id}")
def update_mcp_source(
    source_id: int,
    payload: McpSourceUpdate,
    _admin: UserInfo = Depends(get_current_admin),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    source = _get_source(db, source_id)
    fields = payload.model_fields_set
    if "name" in fields and payload.name is not None:
        _ensure_unique_name(db, payload.name, exclude_id=source.id)
        source.name = payload.name
    if "url" in fields and payload.url is not None:
        source.url = _validate_mcp_url(payload.url)
    for field_name in ("transport", "enabled", "priority"):
        value = getattr(payload, field_name)
        if field_name in fields and value is not None:
            setattr(source, field_name, value)
    if "capabilities" in fields and payload.capabilities is not None:
        source.capability_config_json = _serialize_capabilities(payload.capabilities)
    if not source.credential_reference:
        source.credential_reference = f"MCP_SOURCE_{source.id}"
    store = get_credential_store()
    store.save(
        source.credential_reference,
        api_key=payload.api_key,
        headers=payload.headers,
    )
    db.commit()
    db.refresh(source)
    return _serialize_source(source, store)


@router.post("/mcp-sources/{source_id}/test")
async def test_mcp_source_connection(
    source_id: int,
    _admin: UserInfo = Depends(get_current_admin),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    source = _get_source(db, source_id)
    try:
        headers = get_credential_store().load_headers(source.credential_reference or "")
        result = await build_mcp_client(source, headers).list_tools()
    except Exception:
        return {
            "success": False,
            "message": "连接失败，请检查地址、传输方式和服务端凭据",
            "tools": [],
            "missing_mappings": _configured_tools(source.capability_config_json),
        }

    raw_tools = result.get("tools", []) if isinstance(result, dict) else []
    tool_names = sorted(
        {
            str(tool.get("name", "")).strip()
            for tool in raw_tools
            if isinstance(tool, dict) and str(tool.get("name", "")).strip()
        }
    )
    configured = _configured_tools(source.capability_config_json)
    missing = {
        capability: tool for capability, tool in configured.items() if tool not in tool_names
    }
    if missing:
        return {
            "success": False,
            "message": "连接成功，但能力映射缺少工具",
            "tools": tool_names,
            "missing_mappings": missing,
        }
    return {
        "success": True,
        "message": f"连接成功，发现 {len(tool_names)} 个工具",
        "tools": tool_names,
        "missing_mappings": {},
    }


def _get_source(db: Session, source_id: int) -> McpDataSource:
    source = db.get(McpDataSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="MCP 数据源不存在")
    return source


def _validate_mcp_url(value: str) -> str:
    """验证地址且用固定错误避免在响应中回显可能的凭据。"""
    url = value.strip()
    if not url or len(url) > 1024:
        raise HTTPException(status_code=422, detail="MCP 地址必须是有效的 HTTP 或 HTTPS URL")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=422, detail="MCP 地址必须是有效的 HTTP 或 HTTPS URL")
    if parsed.username or parsed.password or "?" in url or "#" in url:
        raise HTTPException(
            status_code=422,
            detail="MCP 地址不能包含查询参数、凭据或片段",
        )
    return url


def _ensure_unique_name(db: Session, name: str, exclude_id: int | None = None) -> None:
    query = db.query(McpDataSource).filter(McpDataSource.name == name)
    if exclude_id is not None:
        query = query.filter(McpDataSource.id != exclude_id)
    if query.first() is not None:
        raise HTTPException(status_code=409, detail="MCP 数据源名称已存在")


def _serialize_capabilities(
    capabilities: dict[McpCapability, CapabilityConfig],
) -> dict[str, dict[str, Any]]:
    return {
        capability.value: config.model_dump(exclude_none=True)
        for capability, config in capabilities.items()
    }


def _configured_tools(config: Any) -> dict[str, str]:
    if not isinstance(config, dict):
        return {}
    tools = {}
    for capability, mapping in config.items():
        if isinstance(mapping, dict):
            tool = str(mapping.get("tool", "")).strip()
        else:
            tool = str(mapping).strip()
        if tool:
            tools[str(capability)] = tool
    return tools


def _serialize_source(source: McpDataSource, store: EnvCredentialStore) -> dict[str, Any]:
    reference = source.credential_reference or ""
    return {
        "id": source.id,
        "name": source.name,
        "url": source.url,
        "transport": source.transport,
        "enabled": source.enabled,
        "priority": source.priority,
        "capabilities": source.capability_config_json or {},
        "credentials_configured": bool(reference and store.configured(reference)),
        "created_at": _isoformat(source.created_at),
        "updated_at": _isoformat(source.updated_at),
    }


def _isoformat(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


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
