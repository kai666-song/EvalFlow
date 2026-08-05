import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from httpx import AsyncClient


BASE_URL = "http://127.0.0.1:8000"

MODELS = [
    "qwen3.7-flash",
    "glm-5.2",
]

PROMPT = (
    "请使用中文，并用不超过三句话解释"
    "RAG相比直接调用大语言模型有什么优势。"
)

POLL_INTERVAL_SECONDS = 1
MAX_WAIT_SECONDS = 120


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


async def execute_model_task(
    client: AsyncClient,
    model: str,
) -> dict[str, Any]:
    """创建并运行一个指定模型的任务。"""

    create_response = await client.post(
        "/tasks",
        json={
            "prompt": PROMPT,
            "model": model,
        },
    )
    create_response.raise_for_status()

    created_task = create_response.json()
    task_id = created_task["task_id"]

    print(f"\n模型 {model}：任务已创建")
    print(f"task_id：{task_id}")
    print(
        "requested_model："
        f"{created_task['requested_model']}"
    )

    run_response = await client.post(
        f"/tasks/{task_id}/run",
    )
    run_response.raise_for_status()

    event_loop = asyncio.get_running_loop()
    deadline = event_loop.time() + MAX_WAIT_SECONDS

    while True:
        query_response = await client.get(
            f"/tasks/{task_id}",
        )
        query_response.raise_for_status()

        current_task = query_response.json()
        current_status = current_task["status"]

        print(
            f"模型 {model} 当前状态："
            f"{current_status}"
        )

        if current_status in {"SUCCESS", "FAILED"}:
            return current_task

        if event_loop.time() >= deadline:
            raise TimeoutError(
                f"模型 {model} 的任务在"
                f"{MAX_WAIT_SECONDS}秒内没有完成"
            )

        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def main() -> None:
    """依次运行两个模型并保存对比结果。"""

    results: list[dict[str, Any]] = []

    async with AsyncClient(
        base_url=BASE_URL,
        timeout=60.0,
        trust_env=False,
    ) as client:
        for model in MODELS:
            result = await execute_model_task(
                client,
                model,
            )
            results.append(result)

    print("\n========== 模型对比结果 ==========")

    for result in results:
        print(
            "\n请求模型：",
            result["requested_model"],
        )
        print(
            "实际模型：",
            result["model_name"],
        )
        print(
            "任务状态：",
            result["status"],
        )
        print(
            "模型耗时：",
            result["llm_duration_ms"],
            "ms",
        )
        print(
            "输入Token：",
            result["input_tokens"],
        )
        print(
            "输出Token：",
            result["output_tokens"],
        )
        print(
            "推理Token：",
            result["reasoning_tokens"],
        )
        print(
            "总Token：",
            result["total_tokens"],
        )
        print(
            "模型结果：",
            result["result"],
        )
        print(
            "错误信息：",
            result["error"],
        )

    output_path = Path(
        "model_comparison_result.json"
    )

    output_path.write_text(
        json.dumps(
            results,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        "\n完整结果已保存到：",
        output_path.resolve(),
    )


if __name__ == "__main__":
    asyncio.run(main())
