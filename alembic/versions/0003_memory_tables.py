from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_memory_tables"
down_revision = "0002_profit_calculations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_sessions",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversation_sessions_user_id", "conversation_sessions", ["user_id"])
    op.create_index("ix_conversation_sessions_created_at", "conversation_sessions", ["created_at"])
    op.create_index("ix_conversation_sessions_updated_at", "conversation_sessions", ["updated_at"])

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.String(length=128), nullable=True),
        sa.Column("tool_result", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversation_messages_session_id", "conversation_messages", ["session_id"])
    op.create_index("ix_conversation_messages_role", "conversation_messages", ["role"])
    op.create_index("ix_conversation_messages_tool_name", "conversation_messages", ["tool_name"])
    op.create_index("ix_conversation_messages_created_at", "conversation_messages", ["created_at"])

    op.create_table(
        "memory_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=128), nullable=False),
        sa.Column("memory_type", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("vector_status", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_items_scope", "memory_items", ["scope"])
    op.create_index("ix_memory_items_entity_type", "memory_items", ["entity_type"])
    op.create_index("ix_memory_items_entity_id", "memory_items", ["entity_id"])
    op.create_index("ix_memory_items_memory_type", "memory_items", ["memory_type"])
    op.create_index("ix_memory_items_source", "memory_items", ["source"])
    op.create_index("ix_memory_items_vector_status", "memory_items", ["vector_status"])
    op.create_index("ix_memory_items_created_at", "memory_items", ["created_at"])
    op.create_index("ix_memory_items_updated_at", "memory_items", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_memory_items_updated_at", table_name="memory_items")
    op.drop_index("ix_memory_items_created_at", table_name="memory_items")
    op.drop_index("ix_memory_items_vector_status", table_name="memory_items")
    op.drop_index("ix_memory_items_source", table_name="memory_items")
    op.drop_index("ix_memory_items_memory_type", table_name="memory_items")
    op.drop_index("ix_memory_items_entity_id", table_name="memory_items")
    op.drop_index("ix_memory_items_entity_type", table_name="memory_items")
    op.drop_index("ix_memory_items_scope", table_name="memory_items")
    op.drop_table("memory_items")

    op.drop_index("ix_conversation_messages_created_at", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_tool_name", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_role", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_session_id", table_name="conversation_messages")
    op.drop_table("conversation_messages")

    op.drop_index("ix_conversation_sessions_updated_at", table_name="conversation_sessions")
    op.drop_index("ix_conversation_sessions_created_at", table_name="conversation_sessions")
    op.drop_index("ix_conversation_sessions_user_id", table_name="conversation_sessions")
    op.drop_table("conversation_sessions")
