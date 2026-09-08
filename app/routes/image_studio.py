from __future__ import annotations

import base64
import os
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.auth.dependencies import get_current_user
from app.auth.schemas import UserInfo
from app.db.models import ImageAsset, ImagePrompt, ImageWorkflow, ImageWorkflowRun, ImageWorkflowVersion
from app.deps import get_session
from app.image_workflow.providers import build_provider_registry, provider_statuses
from app.image_workflow.service import execute_run, validate_graph


router = APIRouter(prefix="/api/image-studio", tags=["图片工作台"])
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "static" / "generated" / "image-studio"
OUTPUT_URL_PREFIX = "/image-assets"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def get_image_provider_registry() -> dict[str, Any]:
    return build_provider_registry(os.environ)


class WorkflowGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nodes: list[dict[str, Any]] = Field(min_length=1, max_length=100)
    edges: list[dict[str, Any]] = Field(default_factory=list, max_length=300)

    @model_validator(mode="after")
    def valid_graph(self):
        try:
            validate_graph(self.model_dump())
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        return self


class WorkflowCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=256)
    description: str = Field(default="", max_length=2000)
    graph: WorkflowGraph

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("名称不能为空")
        return cleaned


class RunInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=1, max_length=4000)
    image_urls: list[str] = Field(default_factory=list, max_length=3)


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inputs: RunInputs


class PromptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=256)
    category: str = Field(default="custom", min_length=1, max_length=64)
    content: str = Field(min_length=1, max_length=4000)
    negative_prompt: str = Field(default="", max_length=2000)


class AssetMetadataUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purpose: str = Field(default="custom", max_length=64)
    sku: str = Field(default="", max_length=128)
    asin: str = Field(default="", max_length=32)
    status: str = Field(default="draft", pattern="^(draft|candidate|approved)$")


class SimpleGenerationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=1, max_length=4000)
    image_urls: list[str] = Field(default_factory=list, max_length=3)
    mode: str = Field(default="generate", pattern="^(generate|edit)$")
    model: str = Field(default="qwen-image-2.0-pro", max_length=128)
    size: str = Field(default="1024x1024", max_length=32)
    count: int = Field(default=1, ge=1, le=6)
    negative_prompt: str = Field(default="", max_length=2000)


@router.get("/providers")
def list_providers(current_user: UserInfo = Depends(get_current_user)):
    return provider_statuses(os.environ)


@router.get("/prompts")
def list_prompts(db: Session = Depends(get_session), current_user: UserInfo = Depends(get_current_user)):
    prompts = db.scalars(
        select(ImagePrompt)
        .where(ImagePrompt.user_id == current_user.username)
        .order_by(ImagePrompt.updated_at.desc())
        .limit(200)
    ).all()
    return [_prompt_payload(prompt) for prompt in prompts]


@router.post("/prompts", status_code=status.HTTP_201_CREATED)
def create_prompt(body: PromptCreate, db: Session = Depends(get_session), current_user: UserInfo = Depends(get_current_user)):
    prompt = ImagePrompt(user_id=current_user.username, **body.model_dump())
    db.add(prompt)
    db.commit()
    return _prompt_payload(prompt)


@router.put("/prompts/{prompt_id}")
def update_prompt(
    prompt_id: int,
    body: PromptCreate,
    db: Session = Depends(get_session),
    current_user: UserInfo = Depends(get_current_user),
):
    prompt = _owned_prompt(db, prompt_id, current_user.username)
    for field, value in body.model_dump().items():
        setattr(prompt, field, value)
    db.commit()
    return _prompt_payload(prompt)


@router.delete("/prompts/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_prompt(
    prompt_id: int,
    db: Session = Depends(get_session),
    current_user: UserInfo = Depends(get_current_user),
):
    db.delete(_owned_prompt(db, prompt_id, current_user.username))
    db.commit()


@router.post("/generations", status_code=status.HTTP_202_ACCEPTED)
def create_simple_generation(
    body: SimpleGenerationCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
    current_user: UserInfo = Depends(get_current_user),
    providers: dict[str, Any] = Depends(get_image_provider_registry),
):
    if body.mode == "edit" and not body.image_urls:
        raise HTTPException(status_code=422, detail="图片编辑至少需要一张参考图")
    image_urls = _reference_images_as_data_urls(db, current_user.username, body.image_urls)
    workflow = _simple_workflow(db, current_user.username, body)
    run = ImageWorkflowRun(
        workflow_id=workflow.id, workflow_version=workflow.current_version,
        user_id=current_user.username, status="queued",
        input_json={"prompt": body.prompt, "image_urls": image_urls},
    )
    db.add(run)
    db.commit()
    factory = sessionmaker(bind=db.get_bind(), autoflush=False, expire_on_commit=False)
    background_tasks.add_task(execute_run, run.id, factory, providers, _output_dir(), OUTPUT_URL_PREFIX)
    return _run_payload(run)


@router.post("/workflows", status_code=status.HTTP_201_CREATED)
def create_workflow(
    body: WorkflowCreate,
    db: Session = Depends(get_session),
    current_user: UserInfo = Depends(get_current_user),
):
    workflow = ImageWorkflow(
        user_id=current_user.username,
        name=body.name,
        description=body.description,
        current_version=1,
    )
    db.add(workflow)
    db.flush()
    db.add(
        ImageWorkflowVersion(
            workflow_id=workflow.id,
            version=1,
            graph_json=body.graph.model_dump(),
        )
    )
    db.commit()
    return _workflow_summary(workflow)


@router.get("/workflows")
def list_workflows(
    db: Session = Depends(get_session),
    current_user: UserInfo = Depends(get_current_user),
):
    workflows = db.scalars(
        select(ImageWorkflow)
        .where(ImageWorkflow.user_id == current_user.username, ImageWorkflow.status == "active")
        .order_by(ImageWorkflow.updated_at.desc())
    ).all()
    return [_workflow_summary(workflow) for workflow in workflows]


@router.get("/workflows/{workflow_id}")
def get_workflow(
    workflow_id: int,
    db: Session = Depends(get_session),
    current_user: UserInfo = Depends(get_current_user),
):
    workflow = _owned_workflow(db, workflow_id, current_user.username)
    versions = db.scalars(
        select(ImageWorkflowVersion)
        .where(ImageWorkflowVersion.workflow_id == workflow.id)
        .order_by(ImageWorkflowVersion.version.desc())
    ).all()
    current = next(item for item in versions if item.version == workflow.current_version)
    result = _workflow_summary(workflow)
    result.update(
        {
            "graph": current.graph_json,
            "versions": [
                {"version": item.version, "created_at": _iso(item.created_at)} for item in versions
            ],
        }
    )
    return result


@router.put("/workflows/{workflow_id}")
def update_workflow(
    workflow_id: int,
    body: WorkflowCreate,
    db: Session = Depends(get_session),
    current_user: UserInfo = Depends(get_current_user),
):
    workflow = _owned_workflow(db, workflow_id, current_user.username)
    workflow.name = body.name
    workflow.description = body.description
    workflow.current_version += 1
    db.add(
        ImageWorkflowVersion(
            workflow_id=workflow.id,
            version=workflow.current_version,
            graph_json=body.graph.model_dump(),
        )
    )
    db.commit()
    return _workflow_summary(workflow)


@router.post("/workflows/{workflow_id}/archive")
def archive_workflow(
    workflow_id: int,
    db: Session = Depends(get_session),
    current_user: UserInfo = Depends(get_current_user),
):
    workflow = _owned_workflow(db, workflow_id, current_user.username)
    workflow.status = "archived"
    db.commit()
    return {"status": "archived"}


@router.post("/workflows/{workflow_id}/runs", status_code=status.HTTP_202_ACCEPTED)
def create_run(
    workflow_id: int,
    body: RunCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
    current_user: UserInfo = Depends(get_current_user),
    providers: dict[str, Any] = Depends(get_image_provider_registry),
):
    workflow = _owned_workflow(db, workflow_id, current_user.username)
    run = ImageWorkflowRun(
        workflow_id=workflow.id,
        workflow_version=workflow.current_version,
        user_id=current_user.username,
        status="queued",
        input_json=body.inputs.model_dump(),
    )
    db.add(run)
    db.commit()
    factory = sessionmaker(bind=db.get_bind(), autoflush=False, expire_on_commit=False)
    background_tasks.add_task(
        execute_run,
        run.id,
        factory,
        providers,
        _output_dir(),
        OUTPUT_URL_PREFIX,
    )
    return _run_payload(run)


@router.get("/runs")
def list_runs(
    workflow_id: int | None = None,
    db: Session = Depends(get_session),
    current_user: UserInfo = Depends(get_current_user),
):
    query = select(ImageWorkflowRun).where(ImageWorkflowRun.user_id == current_user.username)
    if workflow_id is not None:
        query = query.where(ImageWorkflowRun.workflow_id == workflow_id)
    runs = db.scalars(query.order_by(ImageWorkflowRun.created_at.desc()).limit(100)).all()
    return [_run_payload(run) for run in runs]


@router.get("/runs/{run_id}")
def get_run(
    run_id: int,
    db: Session = Depends(get_session),
    current_user: UserInfo = Depends(get_current_user),
):
    return _run_payload(_owned_run(db, run_id, current_user.username))


@router.post("/runs/{run_id}/cancel")
def cancel_run(
    run_id: int,
    db: Session = Depends(get_session),
    current_user: UserInfo = Depends(get_current_user),
):
    run = _owned_run(db, run_id, current_user.username)
    if run.status not in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="当前任务状态无法取消")
    run.cancel_requested = True
    if run.status == "queued":
        run.status = "cancelled"
        run.completed_at = datetime.now(UTC)
    db.commit()
    return _run_payload(run)


@router.post("/runs/{run_id}/retry", status_code=status.HTTP_202_ACCEPTED)
def retry_run(
    run_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
    current_user: UserInfo = Depends(get_current_user),
    providers: dict[str, Any] = Depends(get_image_provider_registry),
):
    original = _owned_run(db, run_id, current_user.username)
    if original.status not in {"failed", "cancelled"}:
        raise HTTPException(status_code=409, detail="只有失败或已取消任务可以重试")
    run = ImageWorkflowRun(
        workflow_id=original.workflow_id,
        workflow_version=original.workflow_version,
        user_id=original.user_id,
        status="queued",
        input_json=original.input_json,
    )
    db.add(run)
    db.commit()
    factory = sessionmaker(bind=db.get_bind(), autoflush=False, expire_on_commit=False)
    background_tasks.add_task(
        execute_run,
        run.id,
        factory,
        providers,
        _output_dir(),
        OUTPUT_URL_PREFIX,
    )
    return _run_payload(run)


@router.get("/assets")
def list_assets(
    purpose: str | None = None,
    sku: str | None = None,
    db: Session = Depends(get_session),
    current_user: UserInfo = Depends(get_current_user),
):
    assets = db.scalars(
        select(ImageAsset)
        .where(ImageAsset.user_id == current_user.username)
        .order_by(ImageAsset.created_at.desc())
        .limit(200)
    ).all()
    filtered = [asset for asset in assets if not purpose or asset.metadata_json.get("purpose") == purpose]
    if sku:
        filtered = [asset for asset in filtered if asset.metadata_json.get("sku") == sku]
    return [_asset_payload(asset) for asset in filtered]


@router.post("/assets/upload", status_code=status.HTTP_201_CREATED)
async def upload_asset(
    image: UploadFile = File(...),
    purpose: str = Form("reference"),
    sku: str = Form(""),
    asin: str = Form(""),
    db: Session = Depends(get_session),
    current_user: UserInfo = Depends(get_current_user),
):
    content = await image.read(MAX_UPLOAD_BYTES + 1)
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="图片不能为空且不能超过 10MB")
    extension, mime_type = _detect_image(content)
    if extension is None:
        raise HTTPException(status_code=415, detail="仅支持 PNG、JPEG 和 WEBP 图片")
    safe_user = re.sub(r"[^A-Za-z0-9_-]", "_", current_user.username) or "user"
    user_dir = _output_dir() / safe_user
    user_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{extension}"
    (user_dir / filename).write_bytes(content)
    asset = ImageAsset(
        user_id=current_user.username,
        kind="upload",
        filename=filename,
        url=f"{OUTPUT_URL_PREFIX}/{safe_user}/{filename}",
        mime_type=mime_type,
        size_bytes=len(content),
        metadata_json={
            "original_name": image.filename or "", "purpose": purpose,
            "sku": sku.strip(), "asin": asin.strip(), "status": "draft",
        },
    )
    db.add(asset)
    db.commit()
    return _asset_payload(asset)


@router.put("/assets/{asset_id}/metadata")
def update_asset_metadata(
    asset_id: int,
    body: AssetMetadataUpdate,
    db: Session = Depends(get_session),
    current_user: UserInfo = Depends(get_current_user),
):
    asset = db.scalar(select(ImageAsset).where(ImageAsset.id == asset_id, ImageAsset.user_id == current_user.username))
    if asset is None:
        raise HTTPException(status_code=404, detail="素材不存在")
    asset.metadata_json = {**asset.metadata_json, **body.model_dump()}
    db.commit()
    return _asset_payload(asset)


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reference_asset(
    asset_id: int,
    db: Session = Depends(get_session),
    current_user: UserInfo = Depends(get_current_user),
):
    asset = db.scalar(select(ImageAsset).where(ImageAsset.id == asset_id, ImageAsset.user_id == current_user.username))
    if asset is None:
        raise HTTPException(status_code=404, detail="素材不存在")
    safe_user = re.sub(r"[^A-Za-z0-9_-]", "_", current_user.username) or "user"
    user_dir = (_output_dir() / safe_user).resolve()
    file_path = (user_dir / asset.filename).resolve()
    db.delete(asset)
    db.commit()
    if file_path.parent == user_dir and file_path.is_file():
        file_path.unlink()


def _owned_workflow(db: Session, workflow_id: int, username: str) -> ImageWorkflow:
    workflow = db.scalar(
        select(ImageWorkflow).where(
            ImageWorkflow.id == workflow_id,
            ImageWorkflow.user_id == username,
        )
    )
    if workflow is None:
        raise HTTPException(status_code=404, detail="工作流不存在")
    return workflow


def _reference_images_as_data_urls(db: Session, username: str, urls: list[str]) -> list[str]:
    """Convert owned local assets to Data URLs so image editing works without a public host."""
    resolved: list[str] = []
    for url in urls:
        if url.startswith(("data:image/", "https://", "http://")):
            resolved.append(url)
            continue
        asset = db.scalar(
            select(ImageAsset).where(ImageAsset.user_id == username, ImageAsset.url == url)
        )
        if asset is None:
            raise HTTPException(status_code=422, detail="参考图片不存在或无权访问")
        file_path = _output_dir() / re.sub(r"[^A-Za-z0-9_-]", "_", username) / asset.filename
        try:
            content = file_path.read_bytes()
        except OSError as exc:
            raise HTTPException(status_code=404, detail="参考图片文件不存在") from exc
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="参考图片不能超过 10MB")
        encoded = base64.b64encode(content).decode("ascii")
        resolved.append(f"data:{asset.mime_type};base64,{encoded}")
    return resolved


def _simple_workflow(
    db: Session, username: str, body: SimpleGenerationCreate
) -> ImageWorkflow:
    workflow = db.scalar(
        select(ImageWorkflow).where(
            ImageWorkflow.user_id == username, ImageWorkflow.name == "__simple_image_generation__"
        )
    )
    node_type = "qwen.edit" if body.mode == "edit" else "qwen.generate"
    graph = {
        "nodes": [
            {"id": "prompt", "type": "input.prompt", "config": {}},
            {
                "id": "generate", "type": node_type,
                "config": {
                    "model": body.model, "size": body.size, "count": body.count,
                    "negative_prompt": body.negative_prompt,
                },
            },
            {"id": "output", "type": "output.asset", "config": {}},
        ],
        "edges": [{"source": "prompt", "target": "generate"}, {"source": "generate", "target": "output"}],
    }
    if node_type == "qwen.edit":
        graph["nodes"].append({"id": "image", "type": "input.image", "config": {}})
        graph["edges"].append({"source": "image", "target": "generate"})
    if workflow is None:
        workflow = ImageWorkflow(user_id=username, name="__simple_image_generation__", status="system")
        db.add(workflow)
        db.flush()
        db.add(ImageWorkflowVersion(workflow_id=workflow.id, version=1, graph_json=graph))
        db.commit()
        return workflow
    workflow.current_version += 1
    db.add(ImageWorkflowVersion(workflow_id=workflow.id, version=workflow.current_version, graph_json=graph))
    db.commit()
    return workflow


def _owned_prompt(db: Session, prompt_id: int, username: str) -> ImagePrompt:
    prompt = db.scalar(select(ImagePrompt).where(ImagePrompt.id == prompt_id, ImagePrompt.user_id == username))
    if prompt is None:
        raise HTTPException(status_code=404, detail="提示词不存在")
    return prompt


def _owned_run(db: Session, run_id: int, username: str) -> ImageWorkflowRun:
    run = db.scalar(
        select(ImageWorkflowRun).where(
            ImageWorkflowRun.id == run_id,
            ImageWorkflowRun.user_id == username,
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return run


def _workflow_summary(workflow: ImageWorkflow) -> dict[str, Any]:
    return {
        "id": workflow.id,
        "name": workflow.name,
        "description": workflow.description,
        "current_version": workflow.current_version,
        "status": workflow.status,
        "created_at": _iso(workflow.created_at),
        "updated_at": _iso(workflow.updated_at),
    }


def _run_payload(run: ImageWorkflowRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "workflow_id": run.workflow_id,
        "workflow_version": run.workflow_version,
        "status": run.status,
        "inputs": run.input_json,
        "result": run.result_json,
        "node_logs": run.node_log_json,
        "error_summary": run.error_summary,
        "cancel_requested": run.cancel_requested,
        "created_at": _iso(run.created_at),
        "started_at": _iso(run.started_at),
        "completed_at": _iso(run.completed_at),
    }


def _asset_payload(asset: ImageAsset) -> dict[str, Any]:
    return {
        "id": asset.id,
        "run_id": asset.run_id,
        "kind": asset.kind,
        "filename": asset.filename,
        "url": asset.url,
        "mime_type": asset.mime_type,
        "size_bytes": asset.size_bytes,
        "metadata": asset.metadata_json,
        "created_at": _iso(asset.created_at),
    }


def _prompt_payload(prompt: ImagePrompt) -> dict[str, Any]:
    return {
        "id": prompt.id, "name": prompt.name, "category": prompt.category,
        "content": prompt.content, "negative_prompt": prompt.negative_prompt,
        "created_at": _iso(prompt.created_at), "updated_at": _iso(prompt.updated_at),
    }


def _detect_image(content: bytes) -> tuple[str | None, str]:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "jpg", "image/jpeg"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp", "image/webp"
    return None, "application/octet-stream"


def _output_dir() -> Path:
    configured = (os.getenv("IMAGE_STUDIO_OUTPUT_DIR") or "").strip()
    return Path(configured) if configured else OUTPUT_DIR


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
