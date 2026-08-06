from httpx import AsyncClient

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

    