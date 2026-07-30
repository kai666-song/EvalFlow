from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_create_task_without_prompt_returns_422() -> None:
    """创建任务时缺少prompt字段，应返回422。"""

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/tasks",
            json={},
        )

    assert response.status_code == 422

    detail = response.json()["detail"]
    assert detail[0]["loc"] == ["body", "prompt"]
    assert detail[0]["type"] == "missing"


async def test_list_tasks_with_invalid_limit_returns_422() -> None:
    """limit小于1时，应返回422。"""

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/tasks",
            params={"limit": 0},
        )

    assert response.status_code == 422

    detail = response.json()["detail"]
    assert detail[0]["loc"] == ["query", "limit"]
    assert detail[0]["type"] == "greater_than_equal"