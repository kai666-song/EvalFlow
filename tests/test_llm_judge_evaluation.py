import app.evaluators.llm_judge as llm_judge_module

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models import (
    EvaluationResultRecord,
    TaskRecord,
)
from app.llm_models import LLMResult
from app.models import TaskStatus


async def _create_ready_judge_run(
    client: AsyncClient,
    db_session: AsyncSession,
) -> tuple[int, list[str]]:
    dataset_response = await client.post(
        "/datasets",
        json={"name": "llm_judge_dataset"},
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
            "expected_keywords": [],
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

    for task_id in task_ids:
        task = await db_session.get(TaskRecord, task_id)

        assert task is not None

        task.status = TaskStatus.SUCCESS.value
        task.result = (
            "RAG 先检索外部知识，"
            "再让模型据此生成回答。"
        )
        task.error = None

    await db_session.commit()

    return data["evaluation_run_id"], task_ids


async def test_evaluate_run_with_llm_judge(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
) -> None:
    async def fake_process_prompt(
        prompt: str,
        model: str | None = None,
    ) -> LLMResult:
        return LLMResult(
            text=(
                '{"score": 90, '
                '"reason": "回答正确且覆盖核心机制。"}'
            ),
            model="judge-test-model",
            duration_ms=10.0,
            input_tokens=10,
            output_tokens=20,
            reasoning_tokens=0,
            cached_tokens=0,
            total_tokens=30,
        )

    monkeypatch.setattr(
        llm_judge_module,
        "process_prompt",
        fake_process_prompt,
    )

    run_id, task_ids = await _create_ready_judge_run(
        client,
        db_session,
    )

    response = await client.post(
        f"/evaluation-runs/{run_id}/evaluate",
        json={"evaluator": "llm_judge"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["evaluator_name"] == "llm_judge"
    assert data["evaluator_version"] == "1.0"
    assert data["evaluated_tasks"] == 2
    assert data["skipped_tasks"] == []

    assert all(
        item["score"] == 0.9
        for item in data["results"]
    )

    assert all(
        item["evaluator_config"]["judge_model"]
        == "judge-test-model"
        for item in data["results"]
    )

    result = await db_session.execute(
        select(EvaluationResultRecord)
        .where(
            EvaluationResultRecord.task_id.in_(task_ids)
        )
    )

    records = result.scalars().all()

    assert len(records) == 2
    assert all(
        record.evaluator_name == "llm_judge"
        for record in records
    )


async def test_llm_judge_failure_skips_without_changing_task(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
) -> None:
    async def fake_invalid_process_prompt(
        prompt: str,
        model: str | None = None,
    ) -> LLMResult:
        return LLMResult(
            text="invalid json",
            model="judge-test-model",
            duration_ms=10.0,
            input_tokens=10,
            output_tokens=20,
            reasoning_tokens=0,
            cached_tokens=0,
            total_tokens=30,
        )

    monkeypatch.setattr(
        llm_judge_module,
        "process_prompt",
        fake_invalid_process_prompt,
    )

    run_id, task_ids = await _create_ready_judge_run(
        client,
        db_session,
    )

    response = await client.post(
        f"/evaluation-runs/{run_id}/evaluate",
        json={"evaluator": "llm_judge"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["evaluated_tasks"] == 0
    assert len(data["skipped_tasks"]) == 2
    assert all(
        "Evaluator failed" in item["reason"]
        for item in data["skipped_tasks"]
    )

    for task_id in task_ids:
        task = await db_session.get(TaskRecord, task_id)

        assert task is not None
        assert task.status == TaskStatus.SUCCESS.value

    result = await db_session.execute(
        select(EvaluationResultRecord)
        .where(
            EvaluationResultRecord.task_id.in_(task_ids)
        )
    )

    assert result.scalars().all() == []