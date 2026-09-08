from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import ImageAsset, ImageWorkflowRun, ImageWorkflowVersion


ALLOWED_NODE_TYPES = {
    "input.prompt",
    "input.image",
    "qwen.generate",
    "qwen.edit",
    "output.asset",
}
MAX_GENERATED_IMAGE_BYTES = 25 * 1024 * 1024


def validate_graph(graph: dict[str, Any]) -> None:
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("工作流至少需要一个节点")
    if not isinstance(edges, list):
        raise ValueError("工作流连线格式无效")
    node_ids = [str(node.get("id", "")) for node in nodes]
    if any(not node_id for node_id in node_ids) or len(node_ids) != len(set(node_ids)):
        raise ValueError("节点 ID 不能为空或重复")
    for node in nodes:
        if node.get("type") not in ALLOWED_NODE_TYPES:
            raise ValueError(f"不支持的节点类型：{node.get('type')}")
    _topological_nodes(graph)


def execute_run(
    run_id: int,
    session_factory: sessionmaker[Session],
    providers: dict[str, Any],
    output_dir: Path,
    public_url_prefix: str = "/image-assets",
) -> None:
    with session_factory() as session:
        run = session.get(ImageWorkflowRun, run_id)
        if run is None:
            return
        if run.cancel_requested:
            _finish_cancelled(run, session)
            return
        run.status = "running"
        run.started_at = datetime.now(UTC)
        session.commit()

        try:
            version = session.scalar(
                select(ImageWorkflowVersion).where(
                    ImageWorkflowVersion.workflow_id == run.workflow_id,
                    ImageWorkflowVersion.version == run.workflow_version,
                )
            )
            if version is None:
                raise RuntimeError("工作流版本不存在")
            validate_graph(version.graph_json)
            assets = _execute_graph(
                graph=version.graph_json,
                run=run,
                session=session,
                providers=providers,
                output_dir=output_dir,
                public_url_prefix=public_url_prefix,
            )
            run.status = "succeeded"
            run.result_json = {"assets": assets}
            run.completed_at = datetime.now(UTC)
            session.commit()
        except Exception as exc:
            run.status = "failed"
            run.error_summary = str(exc)[:1024]
            run.completed_at = datetime.now(UTC)
            session.commit()


def _execute_graph(
    *,
    graph: dict[str, Any],
    run: ImageWorkflowRun,
    session: Session,
    providers: dict[str, Any],
    output_dir: Path,
    public_url_prefix: str,
) -> list[dict[str, Any]]:
    node_logs: list[dict[str, Any]] = []
    generated_assets: list[dict[str, Any]] = []
    provider_node_count = 0
    for node in _topological_nodes(graph):
        session.refresh(run)
        if run.cancel_requested:
            _finish_cancelled(run, session)
            return []
        node_type = node["type"]
        log = {"node_id": node["id"], "type": node_type, "status": "succeeded"}
        if node_type in {"qwen.generate", "qwen.edit"}:
            provider_node_count += 1
            if provider_node_count > 1:
                raise RuntimeError("当前版本每个工作流只支持一个图片模型节点")
            provider = providers.get("qwen")
            if provider is None:
                raise RuntimeError("未配置 BAILIAN_API_KEY 或 DASHSCOPE_API_KEY，无法调用千问图片模型")
            config = node.get("config") or {}
            prompt = str(run.input_json.get("prompt") or config.get("prompt") or "").strip()
            if not prompt:
                raise RuntimeError("图片模型节点缺少提示词")
            image_urls = list(run.input_json.get("image_urls") or [])
            if node_type == "qwen.edit" and not image_urls:
                raise RuntimeError("图片编辑节点至少需要一张参考图")
            result = provider.generate(
                prompt=prompt,
                model=str(config.get("model") or "qwen-image-2.0-pro"),
                size=str(config.get("size") or "1024x1024"),
                count=max(1, min(int(config.get("count") or 1), 6)),
                image_urls=image_urls,
                negative_prompt=str(config.get("negative_prompt") or ""),
            )
            for image_bytes in result.images:
                generated_assets.append(
                    _save_asset(
                        session=session,
                        run=run,
                        output_dir=output_dir,
                        image_bytes=image_bytes,
                        mime_type=result.mime_type,
                        metadata=result.metadata,
                        public_url_prefix=public_url_prefix,
                    )
                )
            log["output_count"] = len(result.images)
        node_logs.append(log)
        run.node_log_json = node_logs
        session.commit()
    return generated_assets


def _save_asset(
    *,
    session: Session,
    run: ImageWorkflowRun,
    output_dir: Path,
    image_bytes: bytes,
    mime_type: str,
    metadata: dict[str, Any],
    public_url_prefix: str,
) -> dict[str, Any]:
    if not image_bytes or len(image_bytes) > MAX_GENERATED_IMAGE_BYTES:
        raise RuntimeError("图片模型返回了空文件或超过 25MB 的文件")
    safe_user = re.sub(r"[^A-Za-z0-9_-]", "_", run.user_id) or "user"
    user_dir = output_dir / safe_user
    user_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.png"
    (user_dir / filename).write_bytes(image_bytes)
    url = f"{public_url_prefix.rstrip('/')}/{safe_user}/{filename}"
    asset = ImageAsset(
        user_id=run.user_id,
        run_id=run.id,
        kind="generated",
        filename=filename,
        url=url,
        mime_type=mime_type,
        size_bytes=len(image_bytes),
        metadata_json=metadata,
    )
    session.add(asset)
    session.flush()
    return {"id": asset.id, "url": url, "mime_type": mime_type, "size_bytes": len(image_bytes)}


def _topological_nodes(graph: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = {str(node.get("id", "")): node for node in graph.get("nodes", [])}
    indegree = {node_id: 0 for node_id in nodes}
    outgoing = {node_id: [] for node_id in nodes}
    for edge in graph.get("edges", []):
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if source not in nodes or target not in nodes:
            raise ValueError("连线引用了不存在的节点")
        outgoing[source].append(target)
        indegree[target] += 1
    queue = [node_id for node_id, degree in indegree.items() if degree == 0]
    ordered = []
    while queue:
        node_id = queue.pop(0)
        ordered.append(nodes[node_id])
        for target in outgoing[node_id]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if len(ordered) != len(nodes):
        raise ValueError("工作流不能包含循环连线")
    return ordered


def _finish_cancelled(run: ImageWorkflowRun, session: Session) -> None:
    run.status = "cancelled"
    run.completed_at = datetime.now(UTC)
    session.commit()
