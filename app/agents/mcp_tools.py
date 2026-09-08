"""卖家精灵 MCP 工具集成模块。

本模块负责与卖家精灵（SellerSprite）MCP 服务建立连接，并将 MCP 工具
封装为 LangChain 兼容的 tool 对象，供聊天 Agent 调用。

工作流程：
1. 从环境变量读取 MCP 服务地址和认证信息
2. 建立 MCP 会话（initialize → initialized 握手）
3. 获取工具列表 / 调用具体工具
4. 返回结果给 Agent

支持两种模式：
- 有 langchain_mcp_adapters：使用 MultiServerMCPClient 自动管理
- 无 langchain_mcp_adapters：使用内置 StreamableHttpMCPClient 回退
"""
from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any

import httpx
from langchain_core.tools import tool

# ── MCP 协议常量 ──────────────────────────────────────
# 卖家精灵 MCP 默认使用 Streamable HTTP 传输协议
DEFAULT_SELLERSPRITE_TRANSPORT = "streamable_http"
# MCP 协议版本号，用于初始化协商
MCP_PROTOCOL_VERSION = "2025-03-26"


def build_sellersprite_mcp_config(env: Mapping[str, str] | None = None) -> dict[str, Any] | None:
    """从环境变量构建卖家精灵 MCP 服务器配置。

    读取 SELLERSPRITE_MCP_URL（必填）和 SELLERSPRITE_MCP_TRANSPORT，
    返回 langchain MCP 客户端可识别的服务器配置字典。
    如果 URL 未配置，返回 None 表示卖家精灵不可用。
    """
    env = os.environ if env is None else env
    if (env.get("MCP_SERVER_ENABLED") or "true").lower() != "true":
        return None
    url = (env.get("MCP_SERVER_URL") or env.get("SELLERSPRITE_MCP_URL") or "").strip()
    if not url:
        return None

    transport = (
        env.get("MCP_SERVER_TRANSPORT")
        or env.get("SELLERSPRITE_MCP_TRANSPORT")
        or DEFAULT_SELLERSPRITE_TRANSPORT
    ).strip()
    server: dict[str, Any] = {
        "url": url,
        "transport": transport,
    }

    headers = _build_headers(env)
    if headers:
        server["headers"] = headers

    return {"sellersprite": server}


def build_legacy_mcp_data_source(
    env: Mapping[str, str] | None = None,
) -> dict[str, Any] | None:
    """把旧环境配置只读物化为统一运行时数据源。

    能力映射必须由环境变量中的 JSON 显式声明；未声明时保持空配置，
    注册表会返回不支持能力，而不会根据工具名称或描述猜测。
    """
    env = os.environ if env is None else env
    config = build_sellersprite_mcp_config(env)
    if not config:
        return None

    raw_capabilities = (
        env.get("MCP_SERVER_CAPABILITY_CONFIG")
        or env.get("SELLERSPRITE_MCP_CAPABILITY_CONFIG")
        or "{}"
    ).strip()
    capability_config = json.loads(raw_capabilities)
    if not isinstance(capability_config, dict):
        raise ValueError("MCP 能力配置必须是 JSON object")

    server = config["sellersprite"]
    return {
        "id": "seller-sprite",
        "name": "卖家精灵",
        "url": server["url"],
        "transport": server["transport"],
        "headers": server.get("headers", {}),
        "enabled": True,
        "priority": 10,
        "capability_config_json": capability_config,
    }


async def load_sellersprite_mcp_tools(
    env: Mapping[str, str] | None = None,
    *,
    client_factory: Any | None = None,
) -> list[Any]:
    """加载卖家精灵 MCP 工具列表。

    优先使用 langchain_mcp_adapters 的 MultiServerMCPClient；
    如果该库未安装，自动回退到内置的 StreamableHttpMCPClient。
    返回 LangChain 兼容的 tool 对象列表。
    """
    config = build_sellersprite_mcp_config(env)
    if not config:
        return []

    # 尝试使用官方 langchain_mcp_adapters 客户端
    if client_factory is None:
        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
        except ModuleNotFoundError:
            # 回退：用内置精简客户端
            return create_sellersprite_generic_tools(config)
        client_factory = MultiServerMCPClient

    client = client_factory(config)
    tools = await client.get_tools()
    return list(tools)


def create_sellersprite_generic_tools(config: dict[str, Any] | None) -> list[Any]:
    """创建卖家精灵泛化工具（回退方案）。

    当 langchain_mcp_adapters 未安装时，用内置 StreamableHttpMCPClient
    创建两个通用工具：
    - sellersprite_mcp_list_tools：列出所有可用 MCP 工具
    - sellersprite_mcp_call_tool：调用任意一个 MCP 工具
    """
    if not config:
        return []

    server = config["sellersprite"]
    client = StreamableHttpMCPClient(
        url=server["url"],
        headers=server.get("headers", {}),
    )

    @tool
    async def sellersprite_mcp_list_tools() -> str:
        """列出卖家精灵 MCP 当前可用工具。"""
        return json.dumps(await client.list_tools(), ensure_ascii=False)

    @tool
    async def sellersprite_mcp_call_tool(tool_name: str, arguments_json: str = "{}") -> str:
        """调用卖家精灵 MCP 工具。arguments_json 必须是该工具参数的 JSON 字符串。"""
        try:
            arguments = json.loads(arguments_json or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError("arguments_json 必须是合法 JSON 字符串") from exc
        if not isinstance(arguments, dict):
            raise ValueError("arguments_json 必须解析为 JSON object")
        return json.dumps(await client.call_tool(tool_name, arguments), ensure_ascii=False)

    return [sellersprite_mcp_list_tools, sellersprite_mcp_call_tool]


class StreamableHttpMCPClient:
    """Streamable HTTP 传输的 MCP 客户端。

    实现 MCP 协议的完整握手流程：
    1. 发送 initialize 请求（携带协议版本和客户端信息）
    2. 发送 initialized 通知（确认握手完成）
    3. 后续请求附带 Mcp-Session-Id 维持会话

    支持 SSE（Server-Sent Events）格式的响应解析。
    """

    def __init__(self, *, url: str, headers: Mapping[str, str] | None = None) -> None:
        self.url = url
        self.headers = dict(headers or {})
        self.session_id = ""       # 握手后由服务器返回
        self.initialized = False   # 握手完成标志
        self._next_id = 1          # JSON-RPC 请求 ID 递增器

    async def list_tools(self) -> dict[str, Any]:
        """获取 MCP 服务器提供的工具列表。"""
        await self._ensure_initialized()
        return await self._request("tools/list", {})

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """调用指定的 MCP 工具并返回结果。"""
        await self._ensure_initialized()
        return await self._request("tools/call", {"name": name, "arguments": arguments})

    async def _ensure_initialized(self) -> None:
        """确保 MCP 握手已完成（懒初始化）。"""
        if self.initialized:
            return
        # 第一步：发送初始化请求，协商协议版本
        await self._request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "amazon-agent", "version": "0.1.0"},
            },
        )
        # 第二步：发送已初始化通知
        await self._notify("notifications/initialized", {})
        self.initialized = True

    async def _notify(self, method: str, params: dict[str, Any]) -> None:
        """发送 JSON-RPC 通知（无 id，无需响应）。"""
        await self._post({"jsonrpc": "2.0", "method": method, "params": params})

    async def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """发送 JSON-RPC 请求并返回 result 部分。

        自动管理请求 ID 递增，解析响应后检查是否有 error 字段。
        """
        request_id = self._next_id
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        response = await self._post(payload)
        message = _parse_mcp_response(response.text)
        if "error" in message:
            raise RuntimeError(f"MCP error: {message['error']}")
        return message.get("result", {})

    async def _post(self, payload: dict[str, Any]) -> httpx.Response:
        """发送 HTTP POST 请求到 MCP 服务器。

        自动管理会话 ID：首次请求后从响应头提取 Mcp-Session-Id，
        后续请求自动带上该会话 ID。
        """
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            **self.headers,
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(self.url, json=payload, headers=headers)
        response.raise_for_status()

        # 捕获服务器返回的会话 ID
        session_id = response.headers.get("Mcp-Session-Id")
        if session_id:
            self.session_id = session_id
        return response


def _build_headers(env: Mapping[str, str]) -> dict[str, str]:
    """从环境变量构建 MCP 请求所需的 HTTP 头。

    支持两种认证配置方式（优先级从高到低）：
    1. SELLERSPRITE_MCP_HEADERS：JSON 对象，可自定义任意请求头
    2. SELLERSPRITE_API_KEY / SELLERSPRITE_MCP_API_KEY：单独配置 API Key，
       自动拼接为 Authorization 头（默认 Bearer 令牌格式）
    """
    headers: dict[str, str] = {}

    # 方式一：自定义请求头 JSON
    raw_headers = (env.get("MCP_SERVER_HEADERS") or env.get("SELLERSPRITE_MCP_HEADERS") or "").strip()
    if raw_headers:
        loaded = json.loads(raw_headers)
        if not isinstance(loaded, dict):
            raise ValueError("SELLERSPRITE_MCP_HEADERS 必须是 JSON object")
        headers.update({str(key): str(value) for key, value in loaded.items()})

    # 方式二：API Key 自动生成认证头
    api_key = (
        env.get("MCP_SERVER_API_KEY")
        or env.get("SELLERSPRITE_API_KEY")
        or env.get("SELLERSPRITE_MCP_API_KEY")
        or ""
    ).strip()
    if api_key:
        header_name = (env.get("SELLERSPRITE_MCP_AUTH_HEADER") or "secret-key").strip()
        auth_scheme = env.get("SELLERSPRITE_MCP_AUTH_SCHEME", "").strip()
        header_value = f"{auth_scheme} {api_key}".strip() if auth_scheme else api_key
        headers[header_name] = header_value

    return headers


def _parse_mcp_response(text: str) -> dict[str, Any]:
    """解析 MCP 响应文本为 JSON 字典。

    兼容两种响应格式：
    - 纯 JSON：直接解析
    - SSE（Server-Sent Events）：提取 data: 行后解析

    例如 "data: {"result": {...}}\n" → {"result": {...}}
    """
    stripped = text.strip()
    if not stripped:
        return {}

    # 处理 SSE 格式：提取所有 "data:" 行
    if stripped.startswith("data:"):
        data_lines = [
            line.removeprefix("data:").strip()
            for line in stripped.splitlines()
            if line.startswith("data:")
        ]
        stripped = "\n".join(data_lines).strip()

    return json.loads(stripped)
