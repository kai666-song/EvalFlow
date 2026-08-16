from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models import (
    ComparisonRecord,
    EvaluationRunRecord,
    TaskRecord,
)


async def test_create_evaluation_run_creates_comparisons_and_tasks(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """每条 Case 应创建一个 Comparison，并为每个模型创建 Task。"""

    dataset_response = await client.post(
        "/datasets",
        json={
            "name": "rag_eval",
        },
    )

    dataset_id = dataset_response.json()["dataset_id"]

    await client.post(
        f"/datasets/{dataset_id}/cases",
        json={
            "prompt": "什么是RAG？",
            "reference_answer": "RAG结合检索与生成。",
        },
    )

    await client.post(
        f"/datasets/{dataset_id}/cases",
        json={
            "prompt": "RAG为什么能降低幻觉？",
            "reference_answer": "因为可以使用外部知识。",
        },
    )

    response = await client.post(
        "/evaluation-runs",
        json={
            "dataset_id": dataset_id,
            "models": [
                "qwen3.7-flash",
                "glm-5.2",
            ],
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["dataset_id"] == dataset_id
    assert data["total_cases"] == 2
    assert data["total_comparisons"] == 2
    assert data["total_tasks"] == 4
    assert len(data["comparisons"]) == 2

    assert all(
        comparison["total"] == 2
        for comparison in data["comparisons"]
    )

    assert all(
        task["status"] == "PENDING"
        for comparison in data["comparisons"]
        for task in comparison["tasks"]
    )

    evaluation_run = await db_session.get(
        EvaluationRunRecord,
        data["evaluation_run_id"],
    )

    assert evaluation_run is not None
    assert evaluation_run.dataset_id == dataset_id


async def test_evaluation_run_persists_comparison_relationships(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """EvaluationRun、Comparison、Task 应正确建立数据库关系。"""

    dataset_response = await client.post(
        "/datasets",
        json={
            "name": "relationship_test",
        },
    )

    dataset_id = dataset_response.json()["dataset_id"]

    case_response = await client.post(
        f"/datasets/{dataset_id}/cases",
        json={
            "prompt": "测试问题",
        },
    )

    case_id = case_response.json()["case_id"]

    response = await client.post(
        "/evaluation-runs",
        json={
            "dataset_id": dataset_id,
            "models": [
                "qwen3.7-flash",
                "glm-5.2",
            ],
        },
    )

    evaluation_run_id = response.json()["evaluation_run_id"]

    result = await db_session.execute(
        select(ComparisonRecord).where(
            ComparisonRecord.evaluation_run_id
            == evaluation_run_id
        )
    )

    comparisons = result.scalars().all()

    assert len(comparisons) == 1

    comparison = comparisons[0]

    assert comparison.evaluation_case_id == case_id

    task_result = await db_session.execute(
        select(TaskRecord).where(
            TaskRecord.comparison_id == comparison.id
        )
    )

    tasks = task_result.scalars().all()

    assert len(tasks) == 2


async def test_create_evaluation_run_returns_404_for_missing_dataset(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/evaluation-runs",
        json={
            "dataset_id": 999999,
            "models": [
                "qwen3.7-flash",
                "glm-5.2",
            ],
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Dataset not found"


async def test_create_evaluation_run_rejects_empty_dataset(
    client: AsyncClient,
) -> None:
    dataset_response = await client.post(
        "/datasets",
        json={
            "name": "empty_eval",
        },
    )

    dataset_id = dataset_response.json()["dataset_id"]

    response = await client.post(
        "/evaluation-runs",
        json={
            "dataset_id": dataset_id,
            "models": [
                "qwen3.7-flash",
                "glm-5.2",
            ],
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Dataset has no cases"