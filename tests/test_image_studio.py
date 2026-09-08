from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.auth.schemas import UserInfo
from app.db.models import Base
from app.db.session import build_session_factory
from app.deps import get_session
from app.image_workflow.providers import ImageProviderResult
from app.image_workflow.providers import QwenImageProvider
from app.routes import image_studio


class FakeImageProvider:
    def generate(self, **kwargs):
        return ImageProviderResult(
            images=[b"generated-png"],
            metadata={"provider": "qwen", "model": kwargs["model"]},
        )


class FakeResponse:
    def __init__(self, payload=None, content=b""):
        self.payload = payload
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class RecordingHttpClient:
    def __init__(self):
        self.request = None

    def post(self, url, **kwargs):
        self.request = {"url": url, **kwargs}
        return FakeResponse(
            {
                "output": {
                    "choices": [
                        {"message": {"content": [{"image": "https://result/image.png"}]}}
                    ]
                }
            }
        )

    def get(self, url, **kwargs):
        return FakeResponse(content=b"provider-png")


def _graph():
    return {
        "nodes": [
            {"id": "prompt", "type": "input.prompt", "config": {}},
            {
                "id": "generate",
                "type": "qwen.generate",
                "config": {"model": "qwen-image-2.0-pro", "size": "1024x1024", "count": 1},
            },
            {"id": "output", "type": "output.asset", "config": {}},
        ],
        "edges": [
            {"source": "prompt", "target": "generate"},
            {"source": "generate", "target": "output"},
        ],
    }


def _test_client(tmp_path, monkeypatch, username="alice"):
    factory = build_session_factory("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(factory.kw["bind"])
    app = FastAPI()
    app.include_router(image_studio.router)

    def override_session():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = lambda: UserInfo(
        username=username,
        display_name=username.title(),
        role="user",
        is_active=True,
    )
    app.dependency_overrides[image_studio.get_image_provider_registry] = lambda: {
        "qwen": FakeImageProvider(),
        "openai": None,
        "google": None,
    }
    monkeypatch.setattr(image_studio, "OUTPUT_DIR", tmp_path)
    return app, TestClient(app)


def test_workflow_version_and_user_isolation(tmp_path, monkeypatch):
    app, client = _test_client(tmp_path, monkeypatch)
    created = client.post(
        "/api/image-studio/workflows",
        json={"name": "Amazon 主图", "description": "", "graph": _graph()},
    )
    assert created.status_code == 201
    workflow_id = created.json()["id"]

    updated = client.put(
        f"/api/image-studio/workflows/{workflow_id}",
        json={"name": "Amazon 主图 v2", "description": "新版", "graph": _graph()},
    )
    assert updated.status_code == 200
    assert updated.json()["current_version"] == 2

    app.dependency_overrides[get_current_user] = lambda: UserInfo(
        username="bob", display_name="Bob", role="user", is_active=True
    )
    assert client.get("/api/image-studio/workflows").json() == []
    assert client.get(f"/api/image-studio/workflows/{workflow_id}").status_code == 404


def test_run_saves_real_provider_output_as_asset(tmp_path, monkeypatch):
    _, client = _test_client(tmp_path, monkeypatch)
    workflow = client.post(
        "/api/image-studio/workflows",
        json={"name": "场景图", "description": "", "graph": _graph()},
    ).json()

    queued = client.post(
        f"/api/image-studio/workflows/{workflow['id']}/runs",
        json={"inputs": {"prompt": "真实产品摄影"}},
    )
    assert queued.status_code == 202
    run = client.get(f"/api/image-studio/runs/{queued.json()['id']}").json()
    assert run["status"] == "succeeded"
    assert run["error_summary"] is None
    assert len(run["result"]["assets"]) == 1

    assets = client.get("/api/image-studio/assets").json()
    assert len(assets) == 1
    assert (tmp_path / "alice" / assets[0]["filename"]).read_bytes() == b"generated-png"


def test_missing_provider_fails_without_fake_result(tmp_path, monkeypatch):
    app, client = _test_client(tmp_path, monkeypatch)
    app.dependency_overrides[image_studio.get_image_provider_registry] = lambda: {
        "qwen": None,
        "openai": None,
        "google": None,
    }
    workflow = client.post(
        "/api/image-studio/workflows",
        json={"name": "无配置", "description": "", "graph": _graph()},
    ).json()
    queued = client.post(
        f"/api/image-studio/workflows/{workflow['id']}/runs",
        json={"inputs": {"prompt": "不会生成假图"}},
    ).json()
    run = client.get(f"/api/image-studio/runs/{queued['id']}").json()
    assert run["status"] == "failed"
    assert "未配置" in run["error_summary"]
    assert run["result"] == {}
    assert client.get("/api/image-studio/assets").json() == []


def test_rejects_cyclic_graph(tmp_path, monkeypatch):
    _, client = _test_client(tmp_path, monkeypatch)
    graph = _graph()
    graph["edges"].append({"source": "output", "target": "prompt"})
    response = client.post(
        "/api/image-studio/workflows",
        json={"name": "循环", "description": "", "graph": graph},
    )
    assert response.status_code == 422


def test_upload_rejects_non_image(tmp_path, monkeypatch):
    _, client = _test_client(tmp_path, monkeypatch)
    response = client.post(
        "/api/image-studio/assets/upload",
        files={"image": ("note.txt", b"not-an-image", "text/plain")},
    )
    assert response.status_code == 415


def test_qwen_provider_uses_generation_and_edit_contract():
    http_client = RecordingHttpClient()
    provider = QwenImageProvider(
        api_key="secret",
        public_base_url="https://agent.example.com",
        http_client=http_client,
    )
    result = provider.generate(
        prompt="保留产品，替换背景",
        image_urls=["/static/generated/reference.png"],
        size="1024x1024",
        count=2,
    )
    request = http_client.request
    content = request["json"]["input"]["messages"][0]["content"]
    assert request["url"].endswith("/services/aigc/multimodal-generation/generation")
    assert content[0]["image"] == "https://agent.example.com/static/generated/reference.png"
    assert content[1]["text"] == "保留产品，替换背景"
    assert request["json"]["parameters"]["n"] == 2
    assert result.images == [b"provider-png"]


def test_image_studio_frontend_is_wired():
    project_root = Path(__file__).parents[1]
    html = (project_root / "app" / "static" / "index.html").read_text(encoding="utf-8")
    script = (project_root / "app" / "static" / "image-studio.js").read_text(encoding="utf-8")
    canvas_script = (project_root / "app" / "static" / "image-canvas-editor.js").read_text(encoding="utf-8")
    assert 'data-page="image-studio"' in html
    assert 'id="page-image-studio"' in html
    assert '/static/image-studio.js' in html
    assert 'Authorization", `Bearer ${token}`' in script
    assert "qwen-image-2.0-pro" in script
    assert "/static/image-canvas-editor.js" in html
    assert 'type: "raster"' in canvas_script
    assert 'type: "inpaint_mask"' in canvas_script
    assert "composeMask" in canvas_script
    assert "changeViewportZoom" in canvas_script
