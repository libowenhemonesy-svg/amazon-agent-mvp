from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import text


def build_session_factory(database_url: str) -> sessionmaker[Session]:
    connect_args = {}
    engine_kwargs = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    if database_url == "sqlite+pysqlite:///:memory:":
        engine_kwargs["poolclass"] = StaticPool
    engine = create_engine(database_url, connect_args=connect_args, **engine_kwargs)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def ensure_sqlite_dev_schema(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as connection:
        _add_column_if_missing(
            connection,
            "sku_master",
            "lifecycle",
            "VARCHAR(32) NOT NULL DEFAULT 'stable'",
        )
        _add_column_if_missing(
            connection,
            "sku_master",
            "platform_link",
            "VARCHAR(512)",
        )
        _add_column_if_missing(
            connection,
            "sku_master",
            "product_category",
            "VARCHAR(128)",
        )
        _add_column_if_missing(
            connection,
            "sku_master",
            "responsible_agent",
            "VARCHAR(128)",
        )
        _add_column_if_missing(
            connection,
            "sku_master",
            "target_gross_margin",
            "FLOAT NOT NULL DEFAULT 0.4",
        )
        _add_column_if_missing(
            connection,
            "sku_master",
            "replenishment_days",
            "INTEGER NOT NULL DEFAULT 20",
        )
        _add_column_if_missing(
            connection,
            "alert_tasks",
            "rule_context",
            "JSON NOT NULL DEFAULT '{}'",
        )


def _add_column_if_missing(connection, table_name: str, column_name: str, definition: str) -> None:
    existing_columns = {
        row[1] for row in connection.execute(text(f"PRAGMA table_info({table_name})")).all()
    }
    if existing_columns and column_name not in existing_columns:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"))
