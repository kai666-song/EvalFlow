from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models import EvaluationDatasetRecord

async def test_create_dataset_persists_dataset(client: AsyncClient, db_session: AsyncSession) -> None:
    """创建的数据集应正确写入数据库。"""

    response = await client.post(
        "/datasets",
        json={
            "name": "rag_basic_eval",
            "description": "RAG基础能力评测集",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert isinstance(data["dataset_id"], int)
    assert data["dataset_id"] > 0
    assert data["name"] == "rag_basic_eval"
    assert data["description"] == "RAG基础能力评测集"
    assert data["created_at"] is not None

    dataset = await db_session.get(EvaluationDatasetRecord, data["dataset_id"])

    assert dataset is not None
    assert dataset.name == "rag_basic_eval"
    assert dataset.description == "RAG基础能力评测集"


async def test_create_dataset_rejects_blank_name(client: AsyncClient) -> None:
    """数据集名称不能为空。"""

    response = await client.post(
        "/datasets",
        json={
            "name": " ",
        },
    )

    assert response.status_code == 422