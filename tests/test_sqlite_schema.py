from pathlib import Path

from sqlalchemy import create_engine, text

from app.db.models import Base
from app.db.session import build_session_factory, ensure_sqlite_dev_schema


def test_ensure_sqlite_dev_schema_adds_columns_to_existing_local_database(tmp_path: Path):
    db_path = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE sku_master (sku VARCHAR(128) PRIMARY KEY)"))
        conn.execute(
            text(
                "CREATE TABLE alert_tasks ("
                "id INTEGER PRIMARY KEY, date DATE, sku VARCHAR(128), alert_type VARCHAR(64), "
                "severity VARCHAR(16), reason VARCHAR(512), status VARCHAR(32), "
                "agent_result JSON, feishu_sync_status VARCHAR(32), created_at DATETIME)"
            )
        )

    session_factory = build_session_factory(f"sqlite+pysqlite:///{db_path}")
    Base.metadata.create_all(session_factory.kw["bind"])
    ensure_sqlite_dev_schema(session_factory.kw["bind"])

    with session_factory.kw["bind"].connect() as conn:
        sku_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(sku_master)"))}
        alert_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(alert_tasks)"))}

    assert {
        "lifecycle",
        "replenishment_days",
        "platform_link",
        "product_category",
        "responsible_agent",
        "target_gross_margin",
    }.issubset(sku_columns)
    assert "rule_context" in alert_columns
