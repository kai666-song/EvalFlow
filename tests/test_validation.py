from httpx import AsyncClient


async def test_create_task_without_prompt_returns_422(
    client: AsyncClient,
) -> None:
    """创建任务时缺少prompt字段，应返回422。"""

    response = await client.post(
        "/tasks",
        json={},
    )

    assert response.status_code == 422

    detail = response.json()["detail"]

    assert detail[0]["loc"] == ["body", "prompt"]
    assert detail[0]["type"] == "missing"


async def test_list_tasks_with_invalid_limit_returns_422(
    client: AsyncClient,
) -> None:
    """limit小于1时，应返回422。"""

    response = await client.get(
        "/tasks",
        params={"limit": 0},
    )

    assert response.status_code == 422

    detail = response.json()["detail"]

    assert detail[0]["loc"] == ["query", "limit"]
    assert detail[0]["type"] == "greater_than_equal"

async def test_create_task_with_unsupported_model_returns_422(
        client: AsyncClient,
) -> None:
    """不在白名单的模型应被参数校验拒绝。"""

    response = await client.post(
        "/tasks",
        json={
            "prompt": "测试非法模型",
            "model": "unknown-model",
        },
    )

    assert response.status_code == 422

    detail = response.json()["detail"]

    assert detail[0]["loc"] == ["body", "model"]
    assert detail[0]["type"] == "enum"