"""初始化管理员账号 —— 首次部署时运行一次。

用法:
    python scripts/seed_admin.py
    python scripts/seed_admin.py --username admin --password mypass
"""
from __future__ import annotations

import argparse
import os
import sys
from getpass import getpass
from pathlib import Path

# 确保项目根目录在 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.security import hash_password
from app.db.session import build_session_factory
from app.db.models import Base, User
from app.env import load_env_file

load_env_file(Path(__file__).resolve().parents[1] / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+pysqlite:///./amazon_agent.db")

factory = build_session_factory(DATABASE_URL)
Base.metadata.create_all(factory.kw["bind"])

parser = argparse.ArgumentParser(description="创建管理员账号")
parser.add_argument("--username", default="admin")
parser.add_argument("--password", default=None)
parser.add_argument("--role", default="admin", choices=["admin", "user"])
parser.add_argument("--display-name", default=None)
args = parser.parse_args()

password = args.password or getpass(f"请输入 {args.username} 的密码: ")

db = factory()
try:
    existing = db.query(User).filter(User.username == args.username).first()
    if existing:
        print(f"用户 '{args.username}' 已存在 — 跳过")
        sys.exit(0)

    user = User(
        username=args.username,
        hashed_password=hash_password(password),
        display_name=args.display_name or args.username,
        role=args.role,
    )
    db.add(user)
    db.commit()
    print(f"✅ 管理员账号创建成功: {args.username}")
finally:
    db.close()
