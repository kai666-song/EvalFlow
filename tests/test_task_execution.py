from httpx import AsyncClient

import app.main as main_module
from app.llm_models import LLMResult

async def fake_process_prompt(prompt: str, model: str | None=None) -> LLMResult:
    """模拟一次成功的大模型调用。"""

    returned_model = model or "test-dafault-model"

    return LLMResult(
        text=f"测试结果：{prompt}",
        model=returned_model,
        duration_ms=10.0,
        input_tokens=5,
        output_tokens=8,
        reasoning_tokens=0,
        cached_tokens=0,
        total_tokens=13,
    )


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
            "model": "glm-5.2",
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

    assert task["requested_model"] == "glm-5.2"
    assert task["model_name"] == "glm-5.2"
    assert task["llm_duration_ms"] == 10.0
    assert task["input_tokens"] == 5
    assert task["output_tokens"] == 8
    assert task["reasoning_tokens"] == 0
    assert task["cached_tokens"] == 0
    assert task["total_tokens"] == 13


async def fake_failed_process_prompt(prompt: str, model: str | None=None) -> str:
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

    assert task["model_name"] is None
    assert task["llm_duration_ms"] is None
    assert task["input_tokens"] is None
    assert task["output_tokens"] is None
    assert task["reasoning_tokens"] is None
    assert task["cached_tokens"] is None
    assert task["total_tokens"] is None


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