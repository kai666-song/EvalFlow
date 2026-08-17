import asyncio
from time import perf_counter

import httpx


BASE_URL = "http://127.0.0.1:8000"

TERMINAL_STATUSES = {
    "SUCCESS",
    "FAILED",
}


async def main() -> None:
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        timeout=120.0,
        trust_env=False,
    ) as client:

        # 1. 创建 Dataset
        dataset_response = await client.post(
            "/datasets",
            json={
                "name": "batch_smoke_eval",
                "description": "EvalFlow 批量评测真实链路测试",
            },
        )

        dataset_response.raise_for_status()

        dataset_id = dataset_response.json()["dataset_id"]

        print(
            f"dataset_created dataset_id={dataset_id}"
        )

        # 2. 创建 3 条 Evaluation Case
        cases = [
            {
                "prompt": "请用一句话解释RAG是什么。",
                "reference_answer": (
                    "RAG通过检索外部知识并将其作为上下文"
                    "提供给大语言模型生成回答。"
                ),
            },
            {
                "prompt": "请用一句话说明HTTP 404和405的区别。",
                "reference_answer": (
                    "404表示资源不存在，405表示资源存在"
                    "但当前HTTP方法不被允许。"
                ),
            },
            {
                "prompt": "请用一句话解释Python中set的主要作用。",
                "reference_answer": (
                    "set用于存储不重复元素，并支持高效成员判断"
                    "和集合运算。"
                ),
            },
        ]

        for case in cases:
            response = await client.post(
                f"/datasets/{dataset_id}/cases",
                json=case,
            )

            response.raise_for_status()

            data = response.json()

            print(
                "case_created",
                f"case_id={data['case_id']}",
            )

        # 3. 创建 EvaluationRun
        run_create_response = await client.post(
            "/evaluation-runs",
            json={
                "dataset_id": dataset_id,
                "models": [
                    "qwen3.7-flash",
                    "glm-5.2",
                ],
            },
        )

        run_create_response.raise_for_status()

        evaluation_run = run_create_response.json()

        evaluation_run_id = (
            evaluation_run["evaluation_run_id"]
        )

        print(
            f"\nevaluation_run_created "
            f"evaluation_run_id={evaluation_run_id}"
        )

        print(
            f"total_cases="
            f"{evaluation_run['total_cases']}"
        )

        print(
            f"total_comparisons="
            f"{evaluation_run['total_comparisons']}"
        )

        print(
            f"total_tasks="
            f"{evaluation_run['total_tasks']}"
        )

        # 4. 提交整批 EvaluationRun
        start_time = perf_counter()

        run_response = await client.post(
            f"/evaluation-runs/{evaluation_run_id}/run"
        )

        run_response.raise_for_status()

        print("\nevaluation_run_submitted")

        submitted = run_response.json()

        for comparison in submitted["comparisons"]:
            print(
                f"case={comparison['evaluation_case_id']}",
                [
                    task["status"]
                    for task in comparison["tasks"]
                ],
            )

        # 5. 持续轮询整个 EvaluationRun
        while True:
            await asyncio.sleep(1)

            response = await client.get(
                f"/evaluation-runs/{evaluation_run_id}"
            )

            response.raise_for_status()

            evaluation_run = response.json()

            tasks = [
                task
                for comparison
                in evaluation_run["comparisons"]
                for task in comparison["tasks"]
            ]

            statuses = [
                task["status"]
                for task in tasks
            ]

            success_count = sum(
                status == "SUCCESS"
                for status in statuses
            )

            failed_count = sum(
                status == "FAILED"
                for status in statuses
            )

            processing_count = sum(
                status == "PROCESSING"
                for status in statuses
            )

            print(
                "poll",
                f"success={success_count}",
                f"failed={failed_count}",
                f"processing={processing_count}",
            )

            if all(
                status in TERMINAL_STATUSES
                for status in statuses
            ):
                break

        wall_duration_ms = (
            perf_counter() - start_time
        ) * 1000

        # 6. 输出最终结果
        print("\n=== Evaluation Run Result ===")

        print(
            f"evaluation_run_id={evaluation_run_id}"
        )

        print(
            f"wall_duration_ms={wall_duration_ms:.2f}"
        )

        print(
            f"total_cases="
            f"{evaluation_run['total_cases']}"
        )

        print(
            f"total_comparisons="
            f"{evaluation_run['total_comparisons']}"
        )

        print(
            f"total_tasks="
            f"{evaluation_run['total_tasks']}"
        )

        for comparison in evaluation_run["comparisons"]:
            print("\n================================")
            print(
                f"case_id="
                f"{comparison['evaluation_case_id']}"
            )
            print(
                f"comparison_id="
                f"{comparison['comparison_id']}"
            )
            print(
                f"prompt={comparison['prompt']}"
            )

            for task in comparison["tasks"]:
                print("\n---")
                print(
                    f"requested_model="
                    f"{task['requested_model']}"
                )
                print(
                    f"status={task['status']}"
                )
                print(
                    f"llm_duration_ms="
                    f"{task['llm_duration_ms']}"
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