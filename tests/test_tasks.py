from httpx import AsyncClient


async def create_test_task(
        client: AsyncClient,
        prompt: str,
) -> dict:
    """创建测试任务并返回响应数据。"""

    response = await client.post(
        "/tasks",
        json = {"prompt": prompt},
    )

    assert response.status_code == 201

    return response.json()

async def test_create_task_returns_pending_task(
    client: AsyncClient,
) -> None:
    """创建任务后，应返回201和PENDING任务。"""

    response = await client.post(
        "/tasks",
        json={
            "prompt": "分析一个AI模型输出的质量问题",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["task_id"]
    assert data["prompt"] == "分析一个AI模型输出的质量问题"
    assert data["status"] == "PENDING"
    assert data["result"] is None
    assert data["error"] is None
    assert data["created_at"]


async def test_get_created_task(
        client: AsyncClient,
) -> None:
    """创建任务后，应能通过task_id查询同一任务。"""

    create_response = await client.post(
        "/tasks",
        json={
            "prompt": "测试任务创建与查询",
        }
    )

    assert create_response.status_code == 201

    created_task = create_response.json()
    task_id = created_task["task_id"]

    get_response = await client.get(
        f"/tasks/{task_id}",
    )

    assert get_response.status_code == 200

    quried_task = get_response.json()

    assert quried_task["task_id"] == task_id
    assert quried_task["prompt"] == "测试任务创建与查询"
    assert quried_task["status"] == "PENDING"
    assert quried_task["result"] is None
    assert quried_task["error"] is None
    assert quried_task["created_at"]

async def test_get_nonexistent_task_returns_404(
        client: AsyncClient,
) -> None:
    """查询不存在的任务时，应返回404."""

    response = await client.get(
        "/tasks/nonexistent-task-id",
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Task not found",
    }


async def test_list_tasks_returns_newest_first(
        client: AsyncClient,
) -> None:
    """任务列表应按照创建时间倒序返回。"""

    created_tasks = []

    for index in range(3):
        task = await create_test_task(
            client,
            prompt=f"测试任务{index+1}",
        )
        created_tasks.append(task)

    response = await client.get("/tasks")

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 3
    assert data["limit"] == 20
    assert data["offset"] == 0
    assert len(data["items"]) == 3

    return_ids = [
        item["task_id"]
        for item in data["items"]
    ]

    expected_ids = [
        task["task_id"]
        for task in reversed(created_tasks)
    ]

    assert return_ids == expected_ids

async def test_list_tasks_supports_pagination(
    client: AsyncClient,
) -> None:
    """limit和offset应正确控制分页结果。"""

    created_tasks = []

    for index in range(5):
        task = await create_test_task(
            client,
            prompt=f"分页任务{index + 1}",
        )
        created_tasks.append(task)

    expected_tasks = list(reversed(created_tasks))

    first_page_response = await client.get(
        "/tasks",
        params={
            "limit": 2,
            "offset": 0,
        },
    )

    assert first_page_response.status_code == 200

    first_page = first_page_response.json()

    assert first_page["total"] == 5
    assert first_page["limit"] == 2
    assert first_page["offset"] == 0
    assert len(first_page["items"]) == 2

    assert [
        item["task_id"]
        for item in first_page["items"]
    ] == [
        task["task_id"]
        for task in expected_tasks[:2]
    ]

    second_page_response = await client.get(
        "/tasks",
        params={
            "limit": 2,
            "offset": 2,
        },
    )

    assert second_page_response.status_code == 200

    second_page = second_page_response.json()

    assert second_page["total"] == 5
    assert second_page["limit"] == 2
    assert second_page["offset"] == 2
    assert len(second_page["items"]) == 2

    assert [
        item["task_id"]
        for item in second_page["items"]
    ] == [
        task["task_id"]
        for task in expected_tasks[2:4]
    ]

async def test_list_tasks_filters_by_status(
    client: AsyncClient,
) -> None:
    """任务列表应能够按照状态筛选。"""

    await create_test_task(
        client,
        prompt="待处理任务1",
    )

    await create_test_task(
        client,
        prompt="待处理任务2",
    )

    pending_response = await client.get(
        "/tasks",
        params={
            "task_status": "PENDING",
        },
    )

    assert pending_response.status_code == 200

    pending_data = pending_response.json()

    assert pending_data["total"] == 2
    assert len(pending_data["items"]) == 2

    assert all(
        item["status"] == "PENDING"
        for item in pending_data["items"]
    )

    success_response = await client.get(
        "/tasks",
        params={
            "task_status": "SUCCESS",
        },
    )

    assert success_response.status_code == 200

    success_data = success_response.json()

    assert success_data["total"] == 0
    assert success_data["items"] == []