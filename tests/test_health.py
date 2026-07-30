from httpx import ASGITransport, AsyncClient

from app.main import app

async def test_health_check() -> None:
    """健康检查接口应返回200和固定JSON。"""

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get("./health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}