"""FastAPI 认证依赖注入。"""
from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.deps import get_session
from app.auth.schemas import UserInfo
from app.auth.security import decode_access_token
from app.db.models import User

security_scheme = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    """认证路由复用应用初始化的数据库会话，避免登录读到另一套数据库。"""
    yield from get_session()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> UserInfo:
    """从 Authorization header 解析用户，失败抛 401。"""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未提供认证令牌")

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌无效或已过期")

    username: str | None = payload.get("sub")
    if username is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌格式错误")

    user = db.query(User).filter(User.username == username, User.is_active.is_(True)).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")

    return UserInfo(username=user.username, display_name=user.display_name, role=user.role, is_active=user.is_active)


def get_current_admin(current_user: UserInfo = Depends(get_current_user)) -> UserInfo:
    """仅 admin 角色可访问。"""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return current_user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> UserInfo | None:
    """不强制登录，但如果带了有效 token 就解析用户。用于可选的用户上下文。"""
    if credentials is None:
        return None
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        return None
    username: str | None = payload.get("sub")
    if username is None:
        return None
    user = db.query(User).filter(User.username == username, User.is_active.is_(True)).first()
    if user is None:
        return None
    return UserInfo(username=user.username, display_name=user.display_name, role=user.role, is_active=user.is_active)
