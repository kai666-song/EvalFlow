import pytest
from datetime import datetime, timezone

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models import (
    EvaluationResultRecord,
    TaskRecord,
)
from app.models import TaskStatus


async def _create_run_with_case(
    client: AsyncClient,
    db_session: AsyncSession,
    *,
    expected_keywords: list[str],
    answers: list[str],
) -> tuple[int, list[str]]:
    dataset_response = await client.post(
        "/datasets",
        json={"name": "keyword_eval_dataset"},
    )

    dataset_id = dataset_response.json()["dataset_id"]

    case_response = await client.post(
        f"/datasets/{dataset_id}/cases",
        json={
            "prompt": "什么是 RAG？",
            "reference_answer": (
                "RAG 通过检索外部知识，"
                "辅助模型生成回答。"
            ),
            "expected_keywords": expected_keywords,
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

    data = run_response.json()
    task_ids = [
        task["task_id"]
        for comparison in data["comparisons"]
        for task in comparison["tasks"]
    ]

    for task_id, answer in zip(task_ids, answers):
        task = await db_session.get(TaskRecord, task_id)
        assert task is not None

        task.status = TaskStatus.SUCCESS.value
        task.result = answer
        task.error = None

    await db_session.commit()

    return data["evaluation_run_id"], task_ids


async def test_case_persists_expected_keywords(
    client: AsyncClient,
) -> None:
    dataset_response = await client.post(
        "/datasets",
        json={"name": "case_keywords"},
    )

    dataset_id = dataset_response.json()["dataset_id"]

    response = await client.post(
        f"/datasets/{dataset_id}/cases",
        json={
            "prompt": "什么是 RAG？",
            "expected_keywords": [
                "检索",
                "外部知识",
            ],
        },
    )

    assert response.status_code == 201
    assert response.json()["expected_keywords"] == [
        "检索",
        "外部知识",
    ]


async def test_evaluate_run_persists_keyword_results(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    run_id, task_ids = await _create_run_with_case(
        client,
        db_session,
        expected_keywords=[
            "检索",
            "外部知识",
            "生成",
        ],
        answers=[
            "RAG 通过检索外部知识辅助模型生成回答。",
            "RAG 会先检索资料。",
        ],
    )

    response = await client.post(
        f"/evaluation-runs/{run_id}/evaluate"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["evaluator_name"] == "keyword_match"
    assert data["evaluator_version"] == "1.0"
    assert data["evaluated_tasks"] == 2
    assert data["skipped_tasks"] == []

    scores = {
        item["task_id"]: item["score"]
        for item in data["results"]
    }

    assert scores[task_ids[0]] == 1.0
    assert scores[task_ids[1]] == pytest.approx(1 / 3)

    result = await db_session.execute(
        select(EvaluationResultRecord)
        .where(
            EvaluationResultRecord.task_id.in_(task_ids)
        )
    )

    records = result.scalars().all()

    assert len(records) == 2
    assert all(
        record.evaluator_version == "1.0"
        for record in records
    )


async def test_evaluate_run_rejects_unfinished_tasks(
    client: AsyncClient,
) -> None:
    dataset_response = await client.post(
        "/datasets",
        json={"name": "unfinished_run"},
    )

    dataset_id = dataset_response.json()["dataset_id"]

    await client.post(
        f"/datasets/{dataset_id}/cases",
        json={
            "prompt": "测试问题",
            "expected_keywords": ["测试"],
        },
    )

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

    run_id = run_response.json()["evaluation_run_id"]

    response = await client.post(
        f"/evaluation-runs/{run_id}/evaluate"
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Evaluation run has unfinished tasks"
    )


async def test_evaluate_run_skips_failed_task(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    run_id, task_ids = await _create_run_with_case(
        client,
        db_session,
        expected_keywords=["检索"],
        answers=[
            "模型已经完成检索。",
            "该答案会被覆盖。",
        ],
    )

    failed_task = await db_session.get(
        TaskRecord,
        task_ids[1],
    )

    assert failed_task is not None

    failed_task.status = TaskStatus.FAILED.value
    failed_task.result = None
    failed_task.error = "LLM request timed out"

    await db_session.commit()

    response = await client.post(
        f"/evaluation-runs/{run_id}/evaluate"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["evaluated_tasks"] == 1
    assert len(data["skipped_tasks"]) == 1
    assert data["skipped_tasks"][0]["task_id"] == task_ids[1]
    assert "FAILED" in data["skipped_tasks"][0]["reason"]


async def test_evaluate_run_is_idempotent_and_results_are_queryable(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    run_id, task_ids = await _create_run_with_case(
        client,
        db_session,
        expected_keywords=["检索"],
        answers=[
            "该回答包含检索。",
            "该回答也包含检索。",
        ],
    )

    first_response = await client.post(
        f"/evaluation-runs/{run_id}/evaluate"
    )
    second_response = await client.post(
        f"/evaluation-runs/{run_id}/evaluate"
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json()["evaluated_tasks"] == 2

    records_result = await db_session.execute(
        select(EvaluationResultRecord)
        .where(
            EvaluationResultRecord.task_id.in_(task_ids)
        )
    )

    records = records_result.scalars().all()

    assert len(records) == 2

    query_response = await client.get(
        f"/tasks/{task_ids[0]}/evaluation-results"
    )

    assert query_response.status_code == 200
    assert len(query_response.json()) == 1


async def test_evaluator_versions_can_coexist_for_one_task(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    run_id, task_ids = await _create_run_with_case(
        client,
        db_session,
        expected_keywords=["检索"],
        answers=[
            "该回答包含检索。",
            "该回答包含检索。",
        ],
    )

    response = await client.post(
        f"/evaluation-runs/{run_id}/evaluate"
    )

    assert response.status_code == 200

    db_session.add(
        EvaluationResultRecord(
            task_id=task_ids[0],
            evaluator_name="keyword_match",
            evaluator_version="1.1",
            score=1.0,
            passed=True,
            reason="规则升级后的示例结果",
            created_at=datetime.now(timezone.utc),
        )
    )

    await db_session.commit()

    result = await db_session.execute(
        select(EvaluationResultRecord)
        .where(
            EvaluationResultRecord.task_id
            == task_ids[0]
        )
    )

    records = result.scalars().all()

    assert {
        record.evaluator_version
        for record in records
    } == {"1.0", "1.1"}