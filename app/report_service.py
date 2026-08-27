from dataclasses import asdict, dataclass, field

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models import (
    ComparisonRecord,
    EvaluationCaseRecord,
    EvaluationResultRecord,
    TaskRecord,
)
from app.models import BadCaseType, TaskStatus


class EvaluationReportNotReadyError(RuntimeError):
    """EvaluationRun 中仍有未结束的模型任务。"""


@dataclass(frozen=True)
class ReportMetrics:
    total_tasks: int
    successful_tasks: int
    failed_tasks: int
    evaluated_tasks: int
    passed_tasks: int
    quality_failed_tasks: int
    unevaluated_tasks: int

    execution_success_rate: float
    evaluation_coverage: float

    average_score: float | None
    pass_rate: float | None

    average_latency_ms: float | None
    total_tokens: int
    total_input_tokens: int
    total_output_tokens: int
    total_reasoning_tokens: int
    total_cached_tokens: int
    average_total_tokens: float | None


@dataclass(frozen=True)
class ModelReportMetrics(ReportMetrics):
    requested_model: str


@dataclass(frozen=True)
class ReportBadCase:
    issue_type: BadCaseType

    evaluation_case_id: int | None
    comparison_id: int
    task_id: str

    requested_model: str
    prompt: str
    reference_answer: str | None
    model_answer: str | None

    score: float | None
    task_error: str | None
    evaluation_reason: str | None


@dataclass(frozen=True)
class ReportUnassessedCase:
    evaluation_case_id: int | None
    comparison_id: int
    task_id: str

    requested_model: str
    prompt: str
    reference_answer: str | None
    model_answer: str | None
    reason: str


@dataclass(frozen=True)
class ReportSampleTask:
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

    score: float | None
    passed: bool | None
    evaluation_reason: str | None


@dataclass
class ReportSample:
    evaluation_case_id: int | None
    comparison_id: int
    prompt: str
    reference_answer: str | None
    expected_keywords: list[str]
    tasks: list[ReportSampleTask] = field(
        default_factory=list
    )


@dataclass(frozen=True)
class EvaluationRunReport:
    evaluation_run_id: int
    dataset_id: int

    evaluator_name: str
    evaluator_version: str

    overall: ReportMetrics
    models: list[ModelReportMetrics]

    bad_cases: list[ReportBadCase]
    unassessed_cases: list[ReportUnassessedCase]
    samples: list[ReportSample]


@dataclass
class _MetricsAccumulator:
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    evaluated_tasks: int = 0
    passed_tasks: int = 0
    quality_failed_tasks: int = 0

    scores: list[float] = field(default_factory=list)
    latencies_ms: list[float] = field(default_factory=list)
    token_totals: list[int] = field(default_factory=list)
    input_token_totals: list[int] = field(default_factory=list)
    output_token_totals: list[int] = field(default_factory=list)
    reasoning_token_totals: list[int] = field(default_factory=list)
    cached_token_totals: list[int] = field(default_factory=list)

    def observe(
        self,
        task: TaskRecord,
        evaluation_result: EvaluationResultRecord | None,
    ) -> None:
        self.total_tasks += 1

        if task.status == TaskStatus.FAILED.value:
            self.failed_tasks += 1
            return

        if task.status != TaskStatus.SUCCESS.value:
            return

        self.successful_tasks += 1

        if task.llm_duration_ms is not None:
            self.latencies_ms.append(
                task.llm_duration_ms
            )

        if task.total_tokens is not None:
            self.token_totals.append(
                task.total_tokens
            )

        if task.input_tokens is not None:
            self.input_token_totals.append(
                task.input_tokens
            )

        if task.output_tokens is not None:
            self.output_token_totals.append(
                task.output_tokens
            )

        if task.reasoning_tokens is not None:
            self.reasoning_token_totals.append(
                task.reasoning_tokens
            )

        if task.cached_tokens is not None:
            self.cached_token_totals.append(
                task.cached_tokens
            )

        if evaluation_result is None:
            return

        self.evaluated_tasks += 1
        self.scores.append(evaluation_result.score)

        if evaluation_result.passed:
            self.passed_tasks += 1
        else:
            self.quality_failed_tasks += 1

    def build(self) -> ReportMetrics:
        unevaluated_tasks = (
            self.successful_tasks
            - self.evaluated_tasks
        )

        return ReportMetrics(
            total_tasks=self.total_tasks,
            successful_tasks=self.successful_tasks,
            failed_tasks=self.failed_tasks,
            evaluated_tasks=self.evaluated_tasks,
            passed_tasks=self.passed_tasks,
            quality_failed_tasks=(
                self.quality_failed_tasks
            ),
            unevaluated_tasks=unevaluated_tasks,
            execution_success_rate=_rate(
                self.successful_tasks,
                self.total_tasks,
            ),
            evaluation_coverage=_rate(
                self.evaluated_tasks,
                self.successful_tasks,
            ),
            average_score=_average(self.scores),
            pass_rate=(
                _rate(
                    self.passed_tasks,
                    self.evaluated_tasks,
                )
                if self.evaluated_tasks
                else None
            ),
            average_latency_ms=_average(
                self.latencies_ms
            ),
            total_tokens=sum(self.token_totals),
            total_input_tokens=sum(
                self.input_token_totals
            ),
            total_output_tokens=sum(
                self.output_token_totals
            ),
            total_reasoning_tokens=sum(
                self.reasoning_token_totals
            ),
            total_cached_tokens=sum(
                self.cached_token_totals
            ),
            average_total_tokens=_average(
                self.token_totals
            ),
        )


def _rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0

    return numerator / denominator


def _average(
    values: list[int] | list[float],
) -> float | None:
    if not values:
        return None

    return sum(values) / len(values)


async def build_evaluation_run_report(
    session: AsyncSession,
    *,
    evaluation_run_id: int,
    dataset_id: int,
    evaluator_name: str,
    evaluator_version: str,
) -> EvaluationRunReport:
    """实时聚合一次 Run 的模型表现和 Bad Case。"""

    evaluation_result_join = and_(
        EvaluationResultRecord.task_id
        == TaskRecord.task_id,
        EvaluationResultRecord.evaluator_name
        == evaluator_name,
        EvaluationResultRecord.evaluator_version
        == evaluator_version,
    )

    statement = (
        select(
            ComparisonRecord,
            TaskRecord,
            EvaluationCaseRecord,
            EvaluationResultRecord,
        )
        .join(
            TaskRecord,
            TaskRecord.comparison_id
            == ComparisonRecord.id,
        )
        .outerjoin(
            EvaluationCaseRecord,
            EvaluationCaseRecord.id
            == ComparisonRecord.evaluation_case_id,
        )
        .outerjoin(
            EvaluationResultRecord,
            evaluation_result_join,
        )
        .where(
            ComparisonRecord.evaluation_run_id
            == evaluation_run_id
        )
        .order_by(
            ComparisonRecord.id.asc(),
            TaskRecord.created_at.asc(),
        )
    )

    rows = (await session.execute(statement)).all()

    if any(
        task.status in {
            TaskStatus.PENDING.value,
            TaskStatus.PROCESSING.value,
        }
        for _, task, _, _ in rows
    ):
        raise EvaluationReportNotReadyError(
            "Evaluation run has unfinished tasks"
        )

    overall_accumulator = _MetricsAccumulator()

    model_accumulators: dict[
        str,
        _MetricsAccumulator,
    ] = {}

    bad_cases: list[ReportBadCase] = []
    unassessed_cases: list[
        ReportUnassessedCase
    ] = []
    samples_by_comparison: dict[int, ReportSample] = {}

    for (
        comparison,
        task,
        evaluation_case,
        evaluation_result,
    ) in rows:
        requested_model = (
            task.requested_model or "unknown"
        )

        model_accumulator = (
            model_accumulators.setdefault(
                requested_model,
                _MetricsAccumulator(),
            )
        )

        overall_accumulator.observe(
            task,
            evaluation_result,
        )

        model_accumulator.observe(
            task,
            evaluation_result,
        )

        prompt = (
            evaluation_case.prompt
            if evaluation_case is not None
            else task.prompt
        )

        reference_answer = (
            evaluation_case.reference_answer
            if evaluation_case is not None
            else None
        )

        evaluation_case_id = (
            evaluation_case.id
            if evaluation_case is not None
            else None
        )

        sample = samples_by_comparison.setdefault(
            comparison.id,
            ReportSample(
                evaluation_case_id=evaluation_case_id,
                comparison_id=comparison.id,
                prompt=prompt,
                reference_answer=reference_answer,
                expected_keywords=(
                    list(
                        evaluation_case.expected_keywords
                        or []
                    )
                    if evaluation_case is not None
                    else []
                ),
            ),
        )

        sample.tasks.append(
            ReportSampleTask(
                task_id=task.task_id,
                requested_model=requested_model,
                status=TaskStatus(task.status),
                model_answer=task.result,
                task_error=task.error,
                llm_duration_ms=task.llm_duration_ms,
                input_tokens=task.input_tokens,
                output_tokens=task.output_tokens,
                reasoning_tokens=task.reasoning_tokens,
                cached_tokens=task.cached_tokens,
                total_tokens=task.total_tokens,
                score=(
                    evaluation_result.score
                    if evaluation_result is not None
                    else None
                ),
                passed=(
                    evaluation_result.passed
                    if evaluation_result is not None
                    else None
                ),
                evaluation_reason=(
                    evaluation_result.reason
                    if evaluation_result is not None
                    else None
                ),
            )
        )

        if task.status == TaskStatus.FAILED.value:
            bad_cases.append(
                ReportBadCase(
                    issue_type=(
                        BadCaseType.EXECUTION_FAILED
                    ),
                    evaluation_case_id=(
                        evaluation_case_id
                    ),
                    comparison_id=comparison.id,
                    task_id=task.task_id,
                    requested_model=requested_model,
                    prompt=prompt,
                    reference_answer=reference_answer,
                    model_answer=task.result,
                    score=None,
                    task_error=task.error,
                    evaluation_reason=None,
                )
            )
            continue

        if task.status != TaskStatus.SUCCESS.value:
            continue

        if evaluation_result is None:
            unassessed_cases.append(
                ReportUnassessedCase(
                    evaluation_case_id=(
                        evaluation_case_id
                    ),
                    comparison_id=comparison.id,
                    task_id=task.task_id,
                    requested_model=requested_model,
                    prompt=prompt,
                    reference_answer=reference_answer,
                    model_answer=task.result,
                    reason=(
                        "No evaluation result exists for "
                        f"{evaluator_name}/"
                        f"{evaluator_version}"
                    ),
                )
            )
            continue

        if not evaluation_result.passed:
            bad_cases.append(
                ReportBadCase(
                    issue_type=(
                        BadCaseType.QUALITY_FAILED
                    ),
                    evaluation_case_id=(
                        evaluation_case_id
                    ),
                    comparison_id=comparison.id,
                    task_id=task.task_id,
                    requested_model=requested_model,
                    prompt=prompt,
                    reference_answer=reference_answer,
                    model_answer=task.result,
                    score=evaluation_result.score,
                    task_error=None,
                    evaluation_reason=(
                        evaluation_result.reason
                    ),
                )
            )

    overall_metrics = (
        overall_accumulator.build()
    )

    model_metrics = [
        ModelReportMetrics(
            requested_model=requested_model,
            **asdict(accumulator.build()),
        )
        for requested_model, accumulator
        in model_accumulators.items()
    ]

    return EvaluationRunReport(
        evaluation_run_id=evaluation_run_id,
        dataset_id=dataset_id,
        evaluator_name=evaluator_name,
        evaluator_version=evaluator_version,
        overall=overall_metrics,
        models=model_metrics,
        bad_cases=bad_cases,
        unassessed_cases=unassessed_cases,
        samples=list(samples_by_comparison.values()),
    )
