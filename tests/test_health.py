from httpx import AsyncClient


async def test_health_check(client: AsyncClient) -> None:
    """健康检查接口应返回200和固定JSON。"""

    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}