from datetime import datetime, timezone

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models import (
    EvaluationResultRecord,
    TaskRecord,
)
from app.evaluation_service import evaluate_evaluation_run
from app.evaluators.base import (
    BaseEvaluator,
    EvaluationContext,
    EvaluationOutcome,
)
from app.models import TaskStatus


async def _create_ready_run(
    client: AsyncClient,
    db_session: AsyncSession,
) -> tuple[int, list[str]]:
    dataset_response = await client.post(
        "/datasets",
        json={"name": "evaluation_service_reliability"},
    )
    dataset_id = dataset_response.json()["dataset_id"]

    case_response = await client.post(
        f"/datasets/{dataset_id}/cases",
        json={
            "prompt": "什么是 RAG？",
            "reference_answer": "RAG 使用检索结果辅助生成。",
            "expected_keywords": ["检索"],
        },
    )
    assert case_response.status_code == 201

    run_response = await client.post(
        "/evaluation-runs",
        json={
            "dataset_id": dataset_id,
            "models": [
                "qwen3.7-flash",
                "glm-5.2",
            ],
        },
    )
    assert run_response.status_code == 201

    run_data = run_response.json()
    task_ids = [
        task["task_id"]
        for comparison in run_data["comparisons"]
        for task in comparison["tasks"]
    ]

    for task_id in task_ids:
        task = await db_session.get(TaskRecord, task_id)
        assert task is not None
        task.status = TaskStatus.SUCCESS.value
        task.result = "该回答包含检索。"
        task.error = None

    await db_session.commit()

    return run_data["evaluation_run_id"], task_ids


class _UnexpectedFailureEvaluator(BaseEvaluator):
    name = "unexpected_failure"
    version = "1.0"

    async def evaluate(
        self,
        context: EvaluationContext,
    ) -> EvaluationOutcome:
        raise RuntimeError("unexpected evaluator failure")


class _InsertRaceEvaluator(BaseEvaluator):
    name = "insert_race"
    version = "1.0"

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def evaluate(
        self,
        context: EvaluationContext,
    ) -> EvaluationOutcome:
        self._session.add(
            EvaluationResultRecord(
                task_id=context.metadata["task_id"],
                evaluator_name=self.name,
                evaluator_version=self.version,
                score=0.25,
                passed=False,
                reason="Result inserted by a competing request",
                created_at=datetime.now(timezone.utc),
            )
        )
        await self._session.commit()

        return EvaluationOutcome(
            score=1.0,
            passed=True,
            reason="Later duplicate result",
        )


async def test_unexpected_evaluator_failure_is_isolated(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    run_id, task_ids = await _create_ready_run(
        client,
        db_session,
    )

    evaluation = await evaluate_evaluation_run(
        db_session,
        evaluation_run_id=run_id,
        evaluator=_UnexpectedFailureEvaluator(),
    )

    assert evaluation.results == []
    assert len(evaluation.skipped_tasks) == 2
    assert all(
        "RuntimeError" in skipped.reason
        for skipped in evaluation.skipped_tasks
    )

    for task_id in task_ids:
        task = await db_session.get(TaskRecord, task_id)
        assert task is not None
        assert task.status == TaskStatus.SUCCESS.value

    records = await db_session.scalars(
        select(EvaluationResultRecord).where(
            EvaluationResultRecord.task_id.in_(task_ids)
        )
    )
    assert records.all() == []


async def test_evaluation_insert_race_reuses_existing_result(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    run_id, task_ids = await _create_ready_run(
        client,
        db_session,
    )

    evaluation = await evaluate_evaluation_run(
        db_session,
        evaluation_run_id=run_id,
        evaluator=_InsertRaceEvaluator(db_session),
    )

    assert len(evaluation.results) == 2
    assert evaluation.skipped_tasks == []
    assert all(
        result.score == 0.25
        for result in evaluation.results
    )

    records = await db_session.scalars(
        select(EvaluationResultRecord).where(
            EvaluationResultRecord.task_id.in_(task_ids),
            EvaluationResultRecord.evaluator_name
            == "insert_race",
            EvaluationResultRecord.evaluator_version == "1.0",
        )
    )
    assert len(records.all()) == 2
