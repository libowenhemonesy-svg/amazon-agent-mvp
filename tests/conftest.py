from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.testclient import TestClient
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.auth.dependencies import get_current_user
from app.auth.schemas import UserInfo
from app.db.models import Base
from app.db.session import build_session_factory
from app.deps import get_session
from app.routes.settings import router as settings_router
try:
    from app.routes.selection import router as selection_router
except ImportError:
    selection_router = None


@pytest.fixture
def session_factory():
    factory = build_session_factory("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(factory.kw["bind"])
    return factory


@pytest.fixture
def session(session_factory):
    with session_factory() as db_session:
        yield db_session


@pytest.fixture
def app(session_factory):
    test_app = FastAPI()
    static_dir = Path(__file__).parents[1] / "app" / "static"
    test_app.mount("/static", StaticFiles(directory=static_dir), name="static")
    test_app.include_router(settings_router)
    if selection_router is not None:
        test_app.include_router(selection_router)

    def override_session():
        with session_factory() as db_session:
            yield db_session

    test_app.dependency_overrides[get_session] = override_session

    @test_app.get("/__test__/current-user")
    def current_user_probe(current_user: UserInfo = Depends(get_current_user)):
        return {"username": current_user.username, "role": current_user.role}

    @test_app.get("/")
    def dashboard():
        return FileResponse(static_dir / "index.html")

    try:
        yield test_app
    finally:
        test_app.dependency_overrides.clear()


@pytest.fixture
def client(app):
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def _user_info(username: str, role: str) -> UserInfo:
    return UserInfo(
        username=username,
        display_name=username.title(),
        role=role,
        is_active=True,
    )


@pytest.fixture
def client_as_user(app):
    app.dependency_overrides[get_current_user] = lambda: _user_info("alice", "user")
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client_as_admin(app):
    app.dependency_overrides[get_current_user] = lambda: _user_info("admin", "admin")
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
