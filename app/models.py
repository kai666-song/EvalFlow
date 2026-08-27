from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, field_validator, StringConstraints
from typing import Annotated, Any


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


class EvaluatorType(StrEnum):
    """当前平台提供的自动化 Evaluator。"""

    KEYWORD_MATCH = "keyword_match"
    LLM_JUDGE = "llm_judge"


class BadCaseType(StrEnum):
    """Report 中可确认的问题类型。"""

    EXECUTION_FAILED = "EXECUTION_FAILED"
    QUALITY_FAILED = "QUALITY_FAILED"


class EvaluationRunStatus(StrEnum):
    """面向产品界面的 EvaluationRun 汇总状态。"""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    PARTIAL_FAILED = "PARTIAL_FAILED"
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

    expected_keywords: list[
        Annotated[
            str,
            StringConstraints(
                strip_whitespace=True,
                min_length=1,
                max_length=100,
            ),
        ]
    ] = Field(
        default_factory=list,
        max_length=30,
    )

    @field_validator("expected_keywords")
    @classmethod
    def validate_unique_keywords(
        cls,
        keywords: list[str],
    ) -> list[str]:
        """关键词规则应明确且不重复。"""

        normalized_keywords = [
            " ".join(keyword.casefold().split())
            for keyword in keywords
        ]

        if len(normalized_keywords) != len(set(normalized_keywords)):
            raise ValueError(
                "expected_keywords must not contain duplicates"
            )

        return keywords


class EvaluationCaseResponse(BaseModel):
    """单条评测样本响应。"""

    case_id: int
    dataset_id: int
    prompt: str
    reference_answer: str | None
    expected_keywords: list[str]
    created_at: datetime


class EvaluationDatasetDetailResponse(EvaluationDatasetResponse):
    """包含全部评测样本的数据集详情。"""

    total_cases: int = Field(ge=0)
    cases: list[EvaluationCaseResponse]


class EvaluationDatasetSummaryResponse(EvaluationDatasetResponse):
    """用于数据集选择器与概览页的轻量摘要。"""

    total_cases: int = Field(ge=0)


class EvaluationDatasetListResponse(BaseModel):
    """评测数据集列表响应。"""

    items: list[EvaluationDatasetSummaryResponse]
    total: int = Field(ge=0)


class EvaluationRunCreate(BaseModel):
    """创建一次批量模型评测。"""

    dataset_id: int = Field(gt=0)

    models: list[SupportedModel] = Field(min_length=2, max_length=5)

    evaluator: EvaluatorType = EvaluatorType.KEYWORD_MATCH

    max_concurrency: int = Field(
        default=2,
        ge=1,
        le=10,
    )

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
    evaluator_name: str
    evaluator_version: str
    max_concurrency: int = Field(ge=1, le=10)
    created_at: datetime
    total_cases: int = Field(ge=0)
    total_comparisons: int = Field(ge=0)
    total_tasks: int = Field(ge=0)

    comparisons: list[EvaluationRunComparisonResponse]


class EvaluationRunSummaryResponse(BaseModel):
    """概览页使用的一次评测运行摘要。"""

    evaluation_run_id: int
    dataset_id: int
    dataset_name: str
    evaluator_name: str
    evaluator_version: str
    max_concurrency: int = Field(ge=1, le=10)
    created_at: datetime
    models: list[str]

    status: EvaluationRunStatus
    total_tasks: int = Field(ge=0)
    pending_tasks: int = Field(ge=0)
    processing_tasks: int = Field(ge=0)
    successful_tasks: int = Field(ge=0)
    failed_tasks: int = Field(ge=0)


class EvaluationRunListResponse(BaseModel):
    """评测运行列表响应。"""

    items: list[EvaluationRunSummaryResponse]
    total: int = Field(ge=0)


class EvaluationRunEvaluateRequest(BaseModel):
    """指定对一个 EvaluationRun 使用哪种 Evaluator。"""

    evaluator: EvaluatorType = EvaluatorType.KEYWORD_MATCH


class EvaluationResultResponse(BaseModel):
    """单个 Evaluator 对一个 Task 的质量评估结果。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: str
    evaluator_name: str
    evaluator_version: str
    evaluator_config: dict[str, Any] | None
    score: float = Field(ge=0, le=1)
    passed: bool
    reason: str | None
    created_at: datetime


class SkippedEvaluationTaskResponse(BaseModel):
    """没有产生质量结果的 Task 及其原因。"""

    task_id: str
    reason: str


class EvaluationRunEvaluateResponse(BaseModel):
    """提交一次 Run 级评测后的汇总结果。"""

    evaluation_run_id: int
    evaluator_name: str
    evaluator_version: str
    evaluated_tasks: int = Field(ge=0)
    skipped_tasks: list[SkippedEvaluationTaskResponse]
    results: list[EvaluationResultResponse]


class EvaluationReportMetricsResponse(BaseModel):
    """一次 Run 或单个模型的聚合指标。"""

    model_config = ConfigDict(from_attributes=True)

    total_tasks: int = Field(ge=0)
    successful_tasks: int = Field(ge=0)
    failed_tasks: int = Field(ge=0)
    evaluated_tasks: int = Field(ge=0)
    passed_tasks: int = Field(ge=0)
    quality_failed_tasks: int = Field(ge=0)
    unevaluated_tasks: int = Field(ge=0)

    execution_success_rate: float = Field(ge=0, le=1)
    evaluation_coverage: float = Field(ge=0, le=1)

    average_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )

    pass_rate: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )

    average_latency_ms: float | None = Field(
        default=None,
        ge=0,
    )

    total_tokens: int = Field(ge=0)
    total_input_tokens: int = Field(ge=0)
    total_output_tokens: int = Field(ge=0)
    total_reasoning_tokens: int = Field(ge=0)
    total_cached_tokens: int = Field(ge=0)

    average_total_tokens: float | None = Field(
        default=None,
        ge=0,
    )


class EvaluationModelReportResponse(
    EvaluationReportMetricsResponse
):
    """单个 requested_model 的聚合指标。"""

    requested_model: str


class EvaluationReportBadCaseResponse(BaseModel):
    """可确认的执行失败或质量失败 Case。"""

    model_config = ConfigDict(from_attributes=True)

    issue_type: BadCaseType

    evaluation_case_id: int | None
    comparison_id: int
    task_id: str

    requested_model: str
    prompt: str
    reference_answer: str | None
    model_answer: str | None

    score: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )

    task_error: str | None
    evaluation_reason: str | None


class EvaluationReportUnassessedCaseResponse(BaseModel):
    """执行成功但没有指定 Evaluator 结果的 Case。"""

    model_config = ConfigDict(from_attributes=True)

    evaluation_case_id: int | None
    comparison_id: int
    task_id: str

    requested_model: str
    prompt: str
    reference_answer: str | None
    model_answer: str | None
    reason: str


class EvaluationReportTaskResponse(BaseModel):
    """报告中一条模型回答及其质量评估。"""

    model_config = ConfigDict(from_attributes=True)

    task_id: str
    requested_model: str
    status: TaskStatus
    model_answer: str | None
    task_error: str | None

    llm_duration_ms: float | None
    input_tokens: int | None
    output_tokens: int | None
    reasoning_tokens: int | None
    cached_tokens: int | None
    total_tokens: int | None

    score: float | None = Field(default=None, ge=0, le=1)
    passed: bool | None
    evaluation_reason: str | None


class EvaluationReportSampleResponse(BaseModel):
    """同一个 EvaluationCase 下的多模型回答对比。"""

    model_config = ConfigDict(from_attributes=True)

    evaluation_case_id: int | None
    comparison_id: int
    prompt: str
    reference_answer: str | None
    expected_keywords: list[str]
    tasks: list[EvaluationReportTaskResponse]


class EvaluationRunReportResponse(BaseModel):
    """一次 EvaluationRun 的质量与效率报告。"""

    model_config = ConfigDict(from_attributes=True)

    evaluation_run_id: int
    dataset_id: int

    evaluator_name: str
    evaluator_version: str

    overall: EvaluationReportMetricsResponse
    models: list[EvaluationModelReportResponse]

    bad_cases: list[EvaluationReportBadCaseResponse]
    unassessed_cases: list[
        EvaluationReportUnassessedCaseResponse
    ]
    samples: list[EvaluationReportSampleResponse]
