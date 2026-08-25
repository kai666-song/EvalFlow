"""add evaluator config to evaluation results

Revision ID: f6a8c2e4b391
Revises: d17f3c9a6e20
Create Date: 2026-08-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a8c2e4b391"
down_revision: Union[str, Sequence[str], None] = "d17f3c9a6e20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Persist runtime configuration for configurable evaluators."""

    with op.batch_alter_table(
        "evaluation_results"
    ) as batch_op:
        batch_op.add_column(
            sa.Column(
                "evaluator_config",
                sa.JSON(),
                nullable=True,
            )
        )


def downgrade() -> None:
    """Remove evaluator runtime configuration."""

    with op.batch_alter_table(
        "evaluation_results"
    ) as batch_op:
        batch_op.drop_column("evaluator_config")