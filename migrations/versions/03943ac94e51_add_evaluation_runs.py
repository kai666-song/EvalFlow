"""add evaluation runs

Revision ID: 03943ac94e51
Revises: e43d4968494b
Create Date: 2026-08-16 13:40:03.175120

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '03943ac94e51'
down_revision: Union[str, Sequence[str], None] = 'e43d4968494b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # 1. 创建 evaluation_runs 新表
    op.create_table(
        "evaluation_runs",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "dataset_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["evaluation_datasets.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_evaluation_runs_dataset_id",
        "evaluation_runs",
        ["dataset_id"],
        unique=False,
    )

    # 2. 修改已经存在的 comparisons 表
    with op.batch_alter_table("comparisons") as batch_op:
        batch_op.add_column(
            sa.Column(
                "evaluation_run_id",
                sa.Integer(),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "evaluation_case_id",
                sa.Integer(),
                nullable=True,
            )
        )

        batch_op.create_index(
            "ix_comparisons_evaluation_run_id",
            ["evaluation_run_id"],
            unique=False,
        )

        batch_op.create_index(
            "ix_comparisons_evaluation_case_id",
            ["evaluation_case_id"],
            unique=False,
        )

        batch_op.create_foreign_key(
            "fk_comparisons_evaluation_run_id_evaluation_runs",
            "evaluation_runs",
            ["evaluation_run_id"],
            ["id"],
        )

        batch_op.create_foreign_key(
            "fk_comparisons_evaluation_case_id_evaluation_cases",
            "evaluation_cases",
            ["evaluation_case_id"],
            ["id"],
        )


def downgrade() -> None:
    """Downgrade schema."""

    # 1. 先撤销 comparisons 上的关系
    with op.batch_alter_table("comparisons") as batch_op:
        batch_op.drop_constraint(
            "fk_comparisons_evaluation_case_id_evaluation_cases",
            type_="foreignkey",
        )

        batch_op.drop_constraint(
            "fk_comparisons_evaluation_run_id_evaluation_runs",
            type_="foreignkey",
        )

        batch_op.drop_index(
            "ix_comparisons_evaluation_case_id",
        )

        batch_op.drop_index(
            "ix_comparisons_evaluation_run_id",
        )

        batch_op.drop_column(
            "evaluation_case_id",
        )

        batch_op.drop_column(
            "evaluation_run_id",
        )

    # 2. 再删除 evaluation_runs
    op.drop_index(
        "ix_evaluation_runs_dataset_id",
        table_name="evaluation_runs",
    )

    op.drop_table(
        "evaluation_runs",
    )