from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models import ComparisonRecord, TaskRecord

async def test_create_comparison_creates_tasks_for_each_model(
        client: AsyncClient,
) -> None:
    """每个指定模型都应生成一条独立任务。"""

    response = await client.post(
        "/comparisons",
        json={
            "prompt": "请解释RAG的优势",
            "models": [
                "qwen3.7-flash",
                "glm-5.2",
            ],
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["prompt"] == "请解释RAG的优势"
    assert data["total"] == 2
    assert len(data["tasks"]) == 2

    assert isinstance(data["comparison_id"], int)
    assert data["comparison_id"] > 0

    requested_model = {task["requested_model"] for task in data["tasks"]}

    assert requested_model == {
        "qwen3.7-flash",
        "glm-5.2",
    }

    for task in data["tasks"]:
        assert task["status"] == 'PENDING'
        assert task["model_name"] is None
        assert task["result"] is None
        assert task["error"] is None

async def test_create_comparison_persists_task_relationships(
        client: AsyncClient,
        db_session: AsyncSession,
) -> None:
    """Comparison 与其子任务应通过 comparison_id 正确关联。"""

    response = await client.post(
        "/comparisons",
        json={
            "prompt": "比较两个模型",
            "models": [
                "qwen3.7-flash",
                "glm-5.2",
            ],
        },
    )

    assert response.status_code == 201

    data = response.json()
    comparison_id = data["comparison_id"]

    # 1.Comparison 本身确实写入数据库
    comparison = await db_session.get(
        ComparisonRecord,
        comparison_id,
    )

    assert comparison is not None
    assert comparison.prompt == "比较两个模型"

    # 2.查询这个 Comparison 的所有 Task
    result = await db_session.execute(
        select(TaskRecord).where(
            TaskRecord.comparison_id == comparison_id
        )
    )

    tasks = result.scalars().all()

    assert len(tasks) == 2

    # 3.两个 Task 都真正关联到同一个 Comparison
    assert all(task.comparison_id == comparison_id for task in tasks)

    # 4.两个模型都被正确创建
    assert {task.requested_model for task in tasks} == {"qwen3.7-flash", "glm-5.2"}

async def test_get_comparison_returns_tasks(
        client: AsyncClient,
) -> None:
    """应通过 comparison_id 查询对比及全部子任务。"""

    create_response = await client.post(
        "/comparisons",
        json={
            "prompt": "比较模型回答",
            "models": [
                "qwen3.7-flash",
                "glm-5.2",
            ],
        },
    )

    assert create_response.status_code == 201

    comparison_id = create_response.json()["comparison_id"]

    response = await client.get(
        f"/comparisons/{comparison_id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["comparison_id"] == comparison_id
    assert data["prompt"] == "比较模型回答"
    assert data["total"] == 2
    assert len(data["tasks"]) == 2

    assert {task["requested_model"] for task in data["tasks"]} == {"qwen3.7-flash", "glm-5.2"} 

async def test_get_comparison_returns_404_when_not_found(
        client: AsyncClient,
) -> None:
    """查询不存在的 Comparison 应返回404."""

    response = await client.get(
        "/comparisons/999999"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Comparison not found"

async def test_create_comparison_requires_two_models(
        client: AsyncClient,
) -> None:
    """模型对比至少需要两个模型。"""

    response = await client.post(
        "/comparisons",
        json={
            "prompt": "测试单模型请求",
            "models": [
                "qwen3.7-flash",
            ],
        },
    )

    assert response.status_code == 422

async def test_create_comparison_rejects_duplicate_models(
        client: AsyncClient,
) -> None:
    """同一次对比中不允许重复选择模型。"""

    response = await client.post(
        "/comparisons",
        json={
            "prompt": "测试重复模型",
            "models": [
                "glm-5.2",
                "glm-5.2",
            ],
        },
    )

    assert response.status_code == 422

    