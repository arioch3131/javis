"""Baseline schema managed by Alembic.

Revision ID: 0001_baseline_schema
Revises:
Create Date: 2026-04-05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

import ai_content_classifier.models.content_models  # noqa: F401
import ai_content_classifier.models.settings_models  # noqa: F401
from ai_content_classifier.models.base import Base

# revision identifiers, used by Alembic.
revision = "0001_baseline_schema"
down_revision = None
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    if not _has_table(inspector, table_name):
        return False
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()

    # Baseline for clean databases.
    Base.metadata.create_all(bind=bind)

    # Legacy compatibility for databases created before classification_confidence existed.
    inspector = sa.inspect(bind)
    if not _has_column(inspector, "content_items", "classification_confidence"):
        op.add_column(
            "content_items",
            sa.Column("classification_confidence", sa.Float(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name in (
        "collection_contents",
        "content_tags",
        "collections",
        "tags",
        "content_items",
        "app_settings",
    ):
        if _has_table(inspector, table_name):
            op.drop_table(table_name)
