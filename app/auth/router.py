"""认证 API 路由 —— 登录、用户信息、修改密码。"""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin, get_current_user, get_db
from app.auth.schemas import ChangePasswordRequest, LoginRequest, TokenResponse
from app.auth.security import create_access_token, hash_password, verify_password
from app.db.models import User

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.username == body.username).first()
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")

    token = create_access_token(data={"sub": user.username, "role": user.role})
    user.last_login = datetime.now(UTC)
    db.commit()

    return TokenResponse(
        access_token=token,
        username=user.username,
        display_name=user.display_name or user.username,
        role=user.role,
    )


@router.get("/me")
def me(current_user=Depends(get_current_user)):
    return current_user


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == current_user.username).first()
    if user is None or not verify_password(body.old_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="旧密码错误")

    user.hashed_password = hash_password(body.new_password)
    db.commit()
    return {"message": "密码修改成功"}


# ── 管理员接口 ──


@router.get("/admin/users")
def list_users(current_admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [
        {
            "username": u.username,
            "display_name": u.display_name,
            "role": u.role,
            "is_active": u.is_active,
            "last_login": u.last_login.isoformat() if u.last_login else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@router.post("/admin/users")
def create_user(
    body: LoginRequest,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    existing = db.query(User).filter(User.username == body.username).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")

    user = User(
        username=body.username,
        hashed_password=hash_password(body.password),
        display_name=body.username,
    )
    db.add(user)
    db.commit()
    return {"message": "用户创建成功", "username": body.username}
