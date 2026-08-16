from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, field_validator, StringConstraints
from typing import Annotated


class SupportedModel(StrEnum):
    """当前平台允许调用的大模型。"""

    QWEN_3_7_FLASH = "qwen3.7-flash"
    GLM_5_2 = "glm-5.2"


class TaskStatus(StrEnum):
    """AI任务可能处于的状态"""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class TaskCreate(BaseModel):
    prompt: str = Field(
        min_length=1,
        max_length=2000,
    )

    model: SupportedModel = SupportedModel.QWEN_3_7_FLASH

class TaskResponse(BaseModel):
    """服务器返回给客户端的完整任务信息。"""

    model_config = ConfigDict(from_attributes=True)

    task_id: str
    prompt: str
    status: TaskStatus
    model_name: str | None=None
    llm_duration_ms: float | None=None

    input_tokens: int | None=None
    output_tokens: int | None=None
    reasoning_tokens: int | None=None
    cached_tokens: int | None=None
    total_tokens: int | None=None

    result: str | None=None
    error: str | None=None
    created_at: datetime

    requested_model: SupportedModel | None=None

class TaskListResponse(BaseModel):
    """任务列表响应。"""

    items: list[TaskResponse]
    total: int
    limit: int
    offset: int

class ComparisonCreate(BaseModel):
    """创建多模型对比任务的请求。"""

    prompt: str = Field(
        min_length=1,
        max_length=2000,
    )

    models: list[SupportedModel] = Field(
        min_length=2,
        max_length=5,
    )

    @field_validator("models")
    @classmethod
    def validate_unique_models(
        cls,
        models: list[SupportedModel],
    ) -> list[SupportedModel]:
        """同一次对比中不允许重复选择模型。"""

        if len(models) != len(set(models)):
            raise ValueError(
                "models must not contain duplicates"
            )

        return models

class ComparisonResponse(BaseModel):
    """创建多模型对比任务后的响应。"""

    comparison_id: int
    prompt: str
    total: int = Field(ge=0)
    tasks: list[TaskResponse]


class EvaluationDatasetCreate(BaseModel):
    """创建评测数据集时的请求体。"""

    name: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=200,
        ),
    ]

    description: Annotated[
        str,
        StringConstraints(max_length=2000),
    ] | None = None


class EvaluationDatasetResponse(BaseModel):
    """评测数据集响应。"""

    dataset_id: int
    name: str
    description: str | None
    created_at: datetime


class EvaluationCaseCreate(BaseModel):
    """向评测数据集中新增一条评测样本。"""

    prompt: str = Field(
        min_length=1,
        max_length=2000,
    )

    reference_answer: str | None = Field(
        default=None,
        max_length=10000,
    )


class EvaluationCaseResponse(BaseModel):
    """单条评测样本响应。"""

    case_id: int
    dataset_id: int
    prompt: str
    reference_answer: str | None
    created_at: datetime


class EvaluationDatasetDetailResponse(EvaluationDatasetResponse):
    """包含全部评测样本的数据集详情。"""

    total_cases: int = Field(ge=0)
    cases: list[EvaluationCaseResponse]


class EvaluationRunCreate(BaseModel):
    """创建一次批量模型评测。"""

    dataset_id: int = Field(gt=0)

    models: list[SupportedModel] = Field(min_length=2, max_length=5)

    @field_validator("models")
    @classmethod
    def validate_unique_models(cls, models: list[SupportedModel]) -> list[SupportedModel]:
        """同一次评测中不允许重复选择模型。"""

        if len(models) != len(set(models)):
            raise ValueError("models must not contain duplicates")

        return models


class EvaluationRunComparisonResponse(ComparisonResponse):
    """Evaluation Run 中单条 Case 对应的模型比较。"""

    evaluation_case_id: int


class EvaluationRunResponse(BaseModel):
    """一次批量模型评测的创建结果。"""

    evaluation_run_id: int
    dataset_id: int
    total_cases: int = Field(ge=0)
    total_comparisons: int = Field(ge=0)
    total_tasks: int = Field(ge=0)

    comparisons: list[EvaluationRunComparisonResponse]