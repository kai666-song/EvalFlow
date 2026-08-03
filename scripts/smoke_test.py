import asyncio
import json
import sys
from pathlib import Path

from httpx import AsyncClient


BASE_URL = "http://127.0.0.1:8000"
POLL_INTERVAL_SECONDS = 1
MAX_WAIT_SECONDS = 60


# 尽量确保Windows终端正确显示中文。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


async def main() -> None:
    """通过真实HTTP接口完成一次任务创建、执行和查询。"""

    prompt = "请使用中文，并用不超过三句话解释什么是RAG。"

    async with AsyncClient(
        base_url=BASE_URL,
        timeout=60.0,
        trust_env=False,
    ) as client:
        # 第一步：创建任务。
        create_response = await client.post(
            "/tasks",
            json={"prompt": prompt},
        )
        create_response.raise_for_status()

        created_task = create_response.json()
        task_id = created_task["task_id"]

        print("任务已创建：")
        print(
            json.dumps(
                created_task,
                ensure_ascii=False,
                indent=2,
            )
        )

        # 第二步：提交运行。
        run_response = await client.post(
            f"/tasks/{task_id}/run",
        )
        run_response.raise_for_status()

        print("\n任务已提交：")
        print(
            json.dumps(
                run_response.json(),
                ensure_ascii=False,
                indent=2,
            )
        )

        # 第三步：轮询最终状态。
        event_loop = asyncio.get_running_loop()
        deadline = event_loop.time() + MAX_WAIT_SECONDS

        while True:
            query_response = await client.get(
                f"/tasks/{task_id}",
            )
            query_response.raise_for_status()

            current_task = query_response.json()
            current_status = current_task["status"]

            print(f"当前状态：{current_status}")

            if current_status != "PROCESSING":
                break

            if event_loop.time() >= deadline:
                raise TimeoutError(
                    f"任务在{MAX_WAIT_SECONDS}秒内没有完成"
                )

            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    # 同时保存到UTF-8文件，避免终端仍然显示乱码。
    output_path = Path("smoke_result.json")
    output_path.write_text(
        json.dumps(
            current_task,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\n最终结果：")
    print(
        json.dumps(
            current_task,
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"\n结果已保存到：{output_path.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())