from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models import (
    EvaluationResultRecord,
    TaskRecord,
)
from app.models import TaskStatus


async def _create_report_run(
    client: AsyncClient,
    db_session: AsyncSession,
) -> tuple[int, dict[str, str]]:
    dataset_response = await client.post(
        "/datasets",
        json={"name": "report_dataset"},
    )

    dataset_id = dataset_response.json()["dataset_id"]

    for index in range(2):
        response = await client.post(
            f"/datasets/{dataset_id}/cases",
            json={
                "prompt": f"测试问题 {index + 1}",
                "reference_answer": (
                    f"测试问题 {index + 1} 的参考答案"
                ),
                "expected_keywords": ["测试"],
            },
        )

        assert response.status_code == 201

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
    task_ids: dict[str, str] = {}

    for case_index, comparison in enumerate(
        run_data["comparisons"],
        start=1,
    ):
        for task_data in comparison["tasks"]:
            requested_model = (
                task_data["requested_model"]
            )

            key = f"case_{case_index}_{requested_model}"
            task_ids[key] = task_data["task_id"]

    qwen_case_1 = await db_session.get(
        TaskRecord,
        task_ids["case_1_qwen3.7-flash"],
    )

    glm_case_1 = await db_session.get(
        TaskRecord,
        task_ids["case_1_glm-5.2"],
    )

    qwen_case_2 = await db_session.get(
        TaskRecord,
        task_ids["case_2_qwen3.7-flash"],
    )

    glm_case_2 = await db_session.get(
        TaskRecord,
        task_ids["case_2_glm-5.2"],
    )

    assert qwen_case_1 is not None
    assert glm_case_1 is not None
    assert qwen_case_2 is not None
    assert glm_case_2 is not None

    qwen_case_1.status = TaskStatus.SUCCESS.value
    qwen_case_1.result = "Qwen 的高质量回答"
    qwen_case_1.llm_duration_ms = 100.0
    qwen_case_1.total_tokens = 10

    glm_case_1.status = TaskStatus.SUCCESS.value
    glm_case_1.result = "GLM 的低质量回答"
    glm_case_1.llm_duration_ms = 300.0
    glm_case_1.total_tokens = 30

    qwen_case_2.status = TaskStatus.SUCCESS.value
    qwen_case_2.result = "尚未执行目标 Evaluator"
    qwen_case_2.llm_duration_ms = 200.0
    qwen_case_2.total_tokens = 20

    glm_case_2.status = TaskStatus.FAILED.value
    glm_case_2.result = None
    glm_case_2.error = "LLM request timed out"

    now = datetime.now(timezone.utc)

    db_session.add_all(
        [
            EvaluationResultRecord(
                task_id=qwen_case_1.task_id,
                evaluator_name="llm_judge",
                evaluator_version="1.0",
                evaluator_config={
                    "judge_model": "judge-test-model",
                },
                score=0.9,
                passed=True,
                reason="回答正确完整",
                created_at=now,
            ),
            EvaluationResultRecord(
                task_id=glm_case_1.task_id,
                evaluator_name="llm_judge",
                evaluator_version="1.0",
                evaluator_config={
                    "judge_model": "judge-test-model",
                },
                score=0.5,
                passed=False,
                reason="遗漏关键步骤",
                created_at=now,
            ),
            # 不同 Evaluator，不应进入 llm_judge 报告。
            EvaluationResultRecord(
                task_id=qwen_case_2.task_id,
                evaluator_name="keyword_match",
                evaluator_version="1.0",
                evaluator_config=None,
                score=1.0,
                passed=True,
                reason="所有关键词均已命中",
                created_at=now,
            ),
            # 同名但不同版本，也不应进入 1.0 报告。
            EvaluationResultRecord(
                task_id=qwen_case_2.task_id,
                evaluator_name="llm_judge",
                evaluator_version="1.1",
                evaluator_config={
                    "judge_model": "judge-test-model",
                },
                score=1.0,
                passed=True,
                reason="新版本评测结果",
                created_at=now,
            ),
        ]
    )

    await db_session.commit()

    return run_data["evaluation_run_id"], task_ids


async def test_report_aggregates_models_and_bad_cases(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    run_id, task_ids = await _create_report_run(
        client,
        db_session,
    )

    response = await client.get(
        f"/evaluation-runs/{run_id}/report",
        params={
            "evaluator": "llm_judge",
            "evaluator_version": "1.0",
        },
    )

    assert response.status_code == 200

    data = response.json()
    overall = data["overall"]

    assert data["evaluator_name"] == "llm_judge"
    assert data["evaluator_version"] == "1.0"

    assert overall["total_tasks"] == 4
    assert overall["successful_tasks"] == 3
    assert overall["failed_tasks"] == 1
    assert overall["evaluated_tasks"] == 2
    assert overall["passed_tasks"] == 1
    assert overall["quality_failed_tasks"] == 1
    assert overall["unevaluated_tasks"] == 1

    assert overall["execution_success_rate"] == 0.75
    assert overall["evaluation_coverage"] == pytest.approx(
        2 / 3
    )
    assert overall["average_score"] == pytest.approx(0.7)
    assert overall["pass_rate"] == 0.5
    assert overall["average_latency_ms"] == 200.0
    assert overall["total_tokens"] == 60
    assert overall["average_total_tokens"] == 20.0

    models = {
        item["requested_model"]: item
        for item in data["models"]
    }

    qwen = models["qwen3.7-flash"]

    assert qwen["total_tasks"] == 2
    assert qwen["successful_tasks"] == 2
    assert qwen["failed_tasks"] == 0
    assert qwen["evaluated_tasks"] == 1
    assert qwen["passed_tasks"] == 1
    assert qwen["unevaluated_tasks"] == 1
    assert qwen["average_score"] == 0.9
    assert qwen["pass_rate"] == 1.0
    assert qwen["average_latency_ms"] == 150.0
    assert qwen["total_tokens"] == 30

    glm = models["glm-5.2"]

    assert glm["total_tasks"] == 2
    assert glm["successful_tasks"] == 1
    assert glm["failed_tasks"] == 1
    assert glm["evaluated_tasks"] == 1
    assert glm["passed_tasks"] == 0
    assert glm["quality_failed_tasks"] == 1
    assert glm["average_score"] == 0.5
    assert glm["pass_rate"] == 0.0

    bad_cases = data["bad_cases"]

    assert {
        item["issue_type"]
        for item in bad_cases
    } == {
        "EXECUTION_FAILED",
        "QUALITY_FAILED",
    }

    execution_failure = next(
        item
        for item in bad_cases
        if item["issue_type"] == "EXECUTION_FAILED"
    )

    assert (
        execution_failure["task_id"]
        == task_ids["case_2_glm-5.2"]
    )
    assert (
        execution_failure["task_error"]
        == "LLM request timed out"
    )
    assert execution_failure["score"] is None
    assert execution_failure["evaluation_reason"] is None

    quality_failure = next(
        item
        for item in bad_cases
        if item["issue_type"] == "QUALITY_FAILED"
    )

    assert (
        quality_failure["task_id"]
        == task_ids["case_1_glm-5.2"]
    )
    assert quality_failure["score"] == 0.5
    assert quality_failure["task_error"] is None
    assert (
        quality_failure["evaluation_reason"]
        == "遗漏关键步骤"
    )

    assert len(data["unassessed_cases"]) == 1
    assert (
        data["unassessed_cases"][0]["task_id"]
        == task_ids["case_2_qwen3.7-flash"]
    )


async def test_report_returns_zero_coverage_without_results(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    dataset_response = await client.post(
        "/datasets",
        json={"name": "unassessed_report"},
    )

    dataset_id = dataset_response.json()["dataset_id"]

    await client.post(
        f"/datasets/{dataset_id}/cases",
        json={
            "prompt": "测试问题",
            "reference_answer": "参考答案",
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
        task.result = "尚未评测的回答"

    await db_session.commit()

    response = await client.get(
        (
            "/evaluation-runs/"
            f"{run_data['evaluation_run_id']}"
            "/report"
        ),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["overall"]["evaluated_tasks"] == 0
    assert data["overall"]["unevaluated_tasks"] == 2
    assert data["overall"]["evaluation_coverage"] == 0.0
    assert data["overall"]["average_score"] is None
    assert data["overall"]["pass_rate"] is None
    assert len(data["unassessed_cases"]) == 2


async def test_report_rejects_unfinished_run(
    client: AsyncClient,
) -> None:
    dataset_response = await client.post(
        "/datasets",
        json={"name": "unfinished_report"},
    )

    dataset_id = dataset_response.json()["dataset_id"]

    await client.post(
        f"/datasets/{dataset_id}/cases",
        json={"prompt": "测试问题"},
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

    response = await client.get(
        f"/evaluation-runs/{run_id}/report"
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Evaluation run has unfinished tasks"
    )


async def test_report_returns_404_for_missing_run(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/evaluation-runs/999999/report"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Evaluation run not found"
    )