"""add expected keywords to evaluation cases

Revision ID: d17f3c9a6e20
Revises: bc5d3b7424d7
Create Date: 2026-08-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d17f3c9a6e20"
down_revision: Union[str, Sequence[str], None] = "bc5d3b7424d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Persist deterministic keyword criteria for each evaluation case."""

    with op.batch_alter_table("evaluation_cases") as batch_op:
        batch_op.add_column(
            sa.Column(
                "expected_keywords",
                sa.JSON(),
                nullable=True,
            )
        )


def downgrade() -> None:
    """Remove deterministic keyword criteria from evaluation cases."""

    with op.batch_alter_table("evaluation_cases") as batch_op:
        batch_op.drop_column("expected_keywords")