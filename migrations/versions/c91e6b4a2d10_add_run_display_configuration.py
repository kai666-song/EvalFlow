"""add run display configuration

Revision ID: c91e6b4a2d10
Revises: f6a8c2e4b391
Create Date: 2026-08-27 16:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c91e6b4a2d10"
down_revision: str | Sequence[str] | None = "f6a8c2e4b391"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "evaluation_runs",
        sa.Column(
            "evaluator_name",
            sa.String(length=100),
            nullable=False,
            server_default="keyword_match",
        ),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column(
            "evaluator_version",
            sa.String(length=50),
            nullable=False,
            server_default="1.0",
        ),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column(
            "max_concurrency",
            sa.Integer(),
            nullable=False,
            server_default="2",
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "evaluation_runs",
        "max_concurrency",
    )
    op.drop_column(
        "evaluation_runs",
        "evaluator_version",
    )
    op.drop_column(
        "evaluation_runs",
        "evaluator_name",
    )
