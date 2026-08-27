from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models import EvaluationDatasetRecord, EvaluationCaseRecord

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


async def test_create_case_persists_case_for_dataset(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """新增的评测样本应正确关联到指定 Dataset。"""

    dataset_response = await client.post(
        "/datasets",
        json={
            "name": "rag_eval",
            "description": "RAG评测集",
        },
    )

    assert dataset_response.status_code == 201

    dataset_id = dataset_response.json()["dataset_id"]

    response = await client.post(
        f"/datasets/{dataset_id}/cases",
        json={
            "prompt": "什么是RAG？",
            "reference_answer": "RAG结合外部检索与大语言模型生成。",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert isinstance(data["case_id"], int)
    assert data["case_id"] > 0
    assert data["dataset_id"] == dataset_id
    assert data["prompt"] == "什么是RAG？"
    assert (
        data["reference_answer"]
        == "RAG结合外部检索与大语言模型生成。"
    )

    evaluation_case = await db_session.get(
        EvaluationCaseRecord,
        data["case_id"],
    )

    assert evaluation_case is not None
    assert evaluation_case.dataset_id == dataset_id
    assert evaluation_case.prompt == "什么是RAG？"


async def test_create_case_returns_404_when_dataset_not_found(
    client: AsyncClient,
) -> None:
    """不能向不存在的数据集新增评测样本。"""

    response = await client.post(
        "/datasets/999999/cases",
        json={
            "prompt": "测试问题",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Dataset not found"


async def test_create_case_rejects_blank_prompt(
    client: AsyncClient,
) -> None:
    """评测样本的 prompt 不能为空。"""

    dataset_response = await client.post(
        "/datasets",
        json={
            "name": "test_dataset",
        },
    )

    dataset_id = dataset_response.json()["dataset_id"]

    response = await client.post(
        f"/datasets/{dataset_id}/cases",
        json={
            "prompt": "",
        },
    )

    assert response.status_code == 422


async def test_get_dataset_returns_dataset_with_cases(
    client: AsyncClient,
) -> None:
    """查询 Dataset 时应返回其全部评测样本。"""

    dataset_response = await client.post(
        "/datasets",
        json={
            "name": "rag_eval",
            "description": "RAG基础评测集",
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
            "reference_answer": "因为生成过程可以参考外部知识。",
        },
    )

    response = await client.get(
        f"/datasets/{dataset_id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["dataset_id"] == dataset_id
    assert data["name"] == "rag_eval"
    assert data["description"] == "RAG基础评测集"

    assert data["total_cases"] == 2
    assert len(data["cases"]) == 2

    assert data["cases"][0]["prompt"] == "什么是RAG？"
    assert (
        data["cases"][1]["prompt"]
        == "RAG为什么能降低幻觉？"
    )


async def test_get_dataset_returns_empty_cases(
    client: AsyncClient,
) -> None:
    """没有 Case 的 Dataset 应返回空列表，而不是404。"""

    create_response = await client.post(
        "/datasets",
        json={
            "name": "empty_dataset",
        },
    )

    dataset_id = create_response.json()["dataset_id"]

    response = await client.get(
        f"/datasets/{dataset_id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["dataset_id"] == dataset_id
    assert data["total_cases"] == 0
    assert data["cases"] == []


async def test_get_dataset_returns_404_when_not_found(
    client: AsyncClient,
) -> None:
    """查询不存在的数据集应返回404。"""

    response = await client.get(
        "/datasets/999999"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Dataset not found"


async def test_list_datasets_returns_case_counts(
    client: AsyncClient,
) -> None:
    first_response = await client.post(
        "/datasets",
        json={"name": "first_dataset"},
    )
    second_response = await client.post(
        "/datasets",
        json={"name": "second_dataset"},
    )

    first_id = first_response.json()["dataset_id"]
    second_id = second_response.json()["dataset_id"]

    await client.post(
        f"/datasets/{first_id}/cases",
        json={"prompt": "问题一"},
    )
    await client.post(
        f"/datasets/{first_id}/cases",
        json={"prompt": "问题二"},
    )

    response = await client.get("/datasets")

    assert response.status_code == 200

    data = response.json()
    items = {
        item["dataset_id"]: item
        for item in data["items"]
    }

    assert data["total"] == 2
    assert items[first_id]["total_cases"] == 2
    assert items[second_id]["total_cases"] == 0
