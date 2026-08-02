from httpx import AsyncClient

import app.main as main_module


async def fake_process_prompt(prompt: str) -> str:
    """立即返回结果，代替真实的五秒模型处理。"""

    return f"测试结果：{prompt}"


async def test_run_task_successfully(
    client: AsyncClient,
    monkeypatch,
) -> None:
    """运行任务后，任务最终应变为SUCCESS。"""

    monkeypatch.setattr(
        main_module,
        "process_prompt",
        fake_process_prompt,
    )

    create_response = await client.post(
        "/tasks",
        json={
            "prompt": "测试后台任务",
        },
    )

    assert create_response.status_code == 201

    task_id = create_response.json()["task_id"]

    run_response = await client.post(
        f"/tasks/{task_id}/run",
    )

    assert run_response.status_code == 202

    get_response = await client.get(
        f"/tasks/{task_id}",
    )

    assert get_response.status_code == 200

    task = get_response.json()

    assert task["status"] == "SUCCESS"
    assert task["result"] == "测试结果：测试后台任务"
    assert task["error"] is None


async def fake_failed_process_prompt(prompt: str) -> str:
    """模拟模型处理过程中发生异常。"""

    raise ValueError("模拟测试失败")

async def test_run_task_failure(
        client: AsyncClient,
        monkeypatch,
) -> None:
    """模型处理异常时，任务最终应变为FAILED。"""

    monkeypatch.setattr(
        main_module,
        "process_prompt",
        fake_failed_process_prompt,
    )

    create_response = await client.post(
        "/tasks",
        json={
            "prompt": "测试失败任务",
        }
    )

    assert create_response.status_code == 201

    task_id = create_response.json()["task_id"]

    run_response = await client.post(
        f"/tasks/{task_id}/run"
    )

    assert run_response.status_code == 202

    get_response = await client.get(
        f"/tasks/{task_id}"
    )

    assert get_response.status_code == 200

    task = get_response.json()

    assert task["status"] == "FAILED"
    assert task["result"] is None
    assert task["error"] == "模拟测试失败"


async def test_run_nonexistent_task_returns_404(
        client: AsyncClient,
        monkeypatch,
) -> None:
    """运行不存在的任务时，应返回404."""

    response = await client.post(
        "/tasks/nonexistent-task-id/run",
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Task not found",
    }


async def test_run_completed_task_returns_409(
    client: AsyncClient,
    monkeypatch,
) -> None:
    """已经完成的任务不能再次提交运行。"""

    monkeypatch.setattr(
        main_module,
        "process_prompt",
        fake_process_prompt,
    )

    create_response = await client.post(
        "/tasks",
        json={
            "prompt": "测试重复运行",
        },
    )

    assert create_response.status_code == 201

    task_id = create_response.json()["task_id"]

    first_run_response = await client.post(
        f"/tasks/{task_id}/run",
    )

    assert first_run_response.status_code == 202

    task_response = await client.get(
        f"/tasks/{task_id}",
    )

    assert task_response.status_code == 200
    assert task_response.json()["status"] == "SUCCESS"

    second_run_response = await client.post(
        f"/tasks/{task_id}/run",
    )

    assert second_run_response.status_code == 409

    response_data = second_run_response.json()

    assert "detail" in response_data
    assert response_data["detail"]