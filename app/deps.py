"""共享依赖注入"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session, sessionmaker

# 全局会话工厂，由 create_app() 初始化
_session_factory: sessionmaker[Session] | None = None


def init_session_factory(factory: sessionmaker[Session]) -> None:
    """初始化全局会话工厂"""
    global _session_factory
    _session_factory = factory


def get_session() -> Generator[Session, None, None]:
    """获取数据库会话（FastAPI 依赖注入用）"""
    if _session_factory is None:
        raise RuntimeError("Session factory not initialized. Call init_session_factory() first.")
    with _session_factory() as session:
        yield session


def get_session_factory() -> sessionmaker[Session]:
    """获取会话工厂（非依赖注入场景用）"""
    if _session_factory is None:
        raise RuntimeError("Session factory not initialized. Call init_session_factory() first.")
    return _session_factory
