from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models import (
    ComparisonRecord,
    EvaluationCaseRecord,
    EvaluationResultRecord,
    TaskRecord,
)
from app.evaluators.base import (
    BaseEvaluator,
    EvaluationContext,
    EvaluationOutcome,
)
from app.logger import get_logger
from app.models import TaskStatus


logger = get_logger()


class EvaluationRunNotReadyError(RuntimeError):
    """EvaluationRun 中仍存在尚未结束的模型任务。"""


@dataclass(frozen=True)
class SkippedEvaluationTask:
    task_id: str
    reason: str


@dataclass(frozen=True)
class EvaluationRunEvaluation:
    evaluator_name: str
    evaluator_version: str
    results: list[EvaluationResultRecord]
    skipped_tasks: list[SkippedEvaluationTask]


def _select_evaluation_result(
    *,
    task_id: str,
    evaluator_name: str,
    evaluator_version: str,
):
    return (
        select(EvaluationResultRecord)
        .where(
            EvaluationResultRecord.task_id == task_id,
            EvaluationResultRecord.evaluator_name
            == evaluator_name,
            EvaluationResultRecord.evaluator_version
            == evaluator_version,
        )
    )


async def _persist_evaluation_result(
    session: AsyncSession,
    *,
    task_id: str,
    evaluator: BaseEvaluator,
    outcome: EvaluationOutcome,
) -> EvaluationResultRecord:
    statement = (
        sqlite_insert(EvaluationResultRecord)
        .values(
            task_id=task_id,
            evaluator_name=evaluator.name,
            evaluator_version=evaluator.version,
            evaluator_config=evaluator.config,
            score=outcome.score,
            passed=outcome.passed,
            reason=outcome.reason,
            created_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_nothing(
            index_elements=[
                "task_id",
                "evaluator_name",
                "evaluator_version",
            ]
        )
    )

    await session.execute(statement)
    await session.commit()

    result = await session.scalar(
        _select_evaluation_result(
            task_id=task_id,
            evaluator_name=evaluator.name,
            evaluator_version=evaluator.version,
        )
    )

    if result is None:
        raise RuntimeError(
            "Evaluation result could not be persisted"
        )

    return result


async def evaluate_evaluation_run(
    session: AsyncSession,
    *,
    evaluation_run_id: int,
    evaluator: BaseEvaluator,
) -> EvaluationRunEvaluation:
    """对一个已完成 Run 中的全部可评测 Task 执行同一种 Evaluator。"""

    statement = (
        select(
            ComparisonRecord,
            TaskRecord,
            EvaluationCaseRecord,
        )
        .join(
            TaskRecord,
            TaskRecord.comparison_id == ComparisonRecord.id,
        )
        .outerjoin(
            EvaluationCaseRecord,
            EvaluationCaseRecord.id
            == ComparisonRecord.evaluation_case_id,
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
        for _, task, _ in rows
    ):
        raise EvaluationRunNotReadyError(
            "Evaluation run has unfinished tasks"
        )

    results: list[EvaluationResultRecord] = []
    skipped_tasks: list[SkippedEvaluationTask] = []

    for comparison, task, evaluation_case in rows:
        if task.status != TaskStatus.SUCCESS.value:
            skipped_tasks.append(
                SkippedEvaluationTask(
                    task_id=task.task_id,
                    reason=(
                        "Task was not evaluated because "
                        f"its execution status is {task.status}"
                    ),
                )
            )
            continue

        if not task.result:
            skipped_tasks.append(
                SkippedEvaluationTask(
                    task_id=task.task_id,
                    reason=(
                        "Task was not evaluated because "
                        "it has no model answer"
                    ),
                )
            )
            continue

        if evaluation_case is None:
            skipped_tasks.append(
                SkippedEvaluationTask(
                    task_id=task.task_id,
                    reason=(
                        "Task was not evaluated because "
                        "it is not linked to an EvaluationCase"
                    ),
                )
            )
            continue

        context = EvaluationContext(
            question=evaluation_case.prompt,
            reference_answer=(
                evaluation_case.reference_answer
            ),
            model_answer=task.result,
            metadata={
                "task_id": task.task_id,
                "comparison_id": comparison.id,
                "evaluation_case_id": evaluation_case.id,
                "requested_model": task.requested_model,
                "model_name": task.model_name,
                "llm_duration_ms": task.llm_duration_ms,
                "token_usage": {
                    "input_tokens": task.input_tokens,
                    "output_tokens": task.output_tokens,
                    "reasoning_tokens": task.reasoning_tokens,
                    "cached_tokens": task.cached_tokens,
                    "total_tokens": task.total_tokens,
                },
                "expected_keywords": (
                    evaluation_case.expected_keywords or []
                ),
            },
        )

        skip_reason = evaluator.get_skip_reason(context)

        if skip_reason is not None:
            skipped_tasks.append(
                SkippedEvaluationTask(
                    task_id=task.task_id,
                    reason=skip_reason,
                )
            )
            continue

        existing_statement = (
            select(EvaluationResultRecord)
            .where(
                EvaluationResultRecord.task_id
                == task.task_id,
                EvaluationResultRecord.evaluator_name
                == evaluator.name,
                EvaluationResultRecord.evaluator_version
                == evaluator.version,
            )
        )

        existing_result = await session.scalar(
            existing_statement
        )
        await session.commit()

        if existing_result is not None:
            results.append(existing_result)
            continue

        try:
            outcome = await evaluator.evaluate(context)
        except ValueError as exc:
            skipped_tasks.append(
                SkippedEvaluationTask(
                    task_id=task.task_id,
                    reason=f"Evaluator failed: {exc}",
                )
            )
            continue

        except Exception as exc:
            logger.exception(
                "evaluator_failed_unexpected "
                "task_id=%s error_type=%s",
                task.task_id,
                type(exc).__name__,
            )
            skipped_tasks.append(
                SkippedEvaluationTask(
                    task_id=task.task_id,
                    reason=(
                        "Evaluator failed unexpectedly: "
                        f"{type(exc).__name__}"
                    ),
                )
            )
            continue

        evaluation_result = await _persist_evaluation_result(
            session,
            task_id=task.task_id,
            evaluator=evaluator,
            outcome=outcome,
        )

        results.append(evaluation_result)

    await session.commit()

    return EvaluationRunEvaluation(
        evaluator_name=evaluator.name,
        evaluator_version=evaluator.version,
        results=results,
        skipped_tasks=skipped_tasks,
    )