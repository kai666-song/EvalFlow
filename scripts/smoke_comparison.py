import asyncio
from time import perf_counter

import httpx


BASE_URL = "http://127.0.0.1:8000"

TERMINAL_STATUSES = {"SUCCESS", "FAILED"}

async def main() -> None:
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        timeout=60.0,
        trust_env=False,
    ) as client:
        # 1.创建一次 comparison
        create_response = await client.post(
            "/comparisons",
            json={
                "prompt": "请用三句话解释RAG的核心工作原理",
                "models": ["qwen3.7-flash", "glm-5.2"],
            },
        )

        create_response.raise_for_status()

        comparison = create_response.json()

        comparison_id = comparison["comparison_id"]

        print(
            f"comparison_created"
            f"comparison_id={comparison_id}"
        )

        for task in comparison["tasks"]:
            print(
                "created",
                task["task_id"],
                task["requested_model"],
                task["status"],
            )

        # 2.提交整组模型执行
        start_time = perf_counter()

        run_response = await client.post(
            f"/comparisons/{comparison_id}/run"
        )

        run_response.raise_for_status()

        print("\ncomparison_submitted")

        for task in run_response.json()["tasks"]:
            print(
                "submitted",
                task["requested_model"],
                task["status"],
            )

        # 3.不断轮询 Comparison
        while True:
            await asyncio.sleep(1)

            response = await client.get(
                f"/comparisons/{comparison_id}"
            )

            response.raise_for_status()

            comparison = response.json()
            tasks = comparison["tasks"]

            statuses = [task["status"] for task in tasks]

            print("poll", statuses)

            if all(task["status"] in TERMINAL_STATUSES for task in tasks):
                break

        wall_duration_ms = (perf_counter() - start_time) * 1000

        # 4.输出最终比较结果
        print("\n=== Comparison Result ===")
        print(f"comparison_id={comparison_id}")
        print(f"wall_duration_ms={wall_duration_ms:.2f}")

        for task in tasks:
            print("\n---")
            print(
                f"requested_model="
                f"{task['requested_model']}"
            )
            print(
                f"status={task['status']}"
            )
            print(
                f"model_name={task['model_name']}"
            )
            print(
                f"llm_duration_ms="
                f"{task['llm_duration_ms']}"
            )
            print(
                f"input_tokens="
                f"{task['input_tokens']}"
            )
            print(
                f"output_tokens="
                f"{task['output_tokens']}"
            )
            print(
                f"reasoning_tokens="
                f"{task['reasoning_tokens']}"
            )
            print(
                f"total_tokens="
                f"{task['total_tokens']}"
            )
            print(
                f"error={task['error']}"
            )
            print(
                f"result={task['result']}"
            )

if __name__ == "__main__":
    asyncio.run(main())

             