from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models import TaskStatus


class EvaluationDatasetRecord(Base):
    """数据库中的评测数据集记录。"""

    __tablename__ = "evaluation_datasets"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class EvaluationCaseRecord(Base):
    """评测数据集中的单条评测样本。"""

    __tablename__ = "evaluation_cases"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_datasets.id"),
        nullable=False,
        index=True,
    )

    prompt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    reference_answer: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    
class ComparisonRecord(Base):
    """数据库中的多模型比较记录。"""
    
    __tablename__ = "comparisons"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    prompt: Mapped[str] = mapped_column(Text, nullable=False)

class TaskRecord(Base):
    """数据库中的AI任务记录。"""

    __tablename__ = "tasks"

    task_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )

    prompt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=TaskStatus.PENDING.value,
    )

    requested_model: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    model_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    llm_duration_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    input_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    output_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    reasoning_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    cached_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    total_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    result: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )   

    comparison_id: Mapped[int | None] = mapped_column(
        ForeignKey("comparisons.id"),
        nullable=True,
        index=True,
    )

