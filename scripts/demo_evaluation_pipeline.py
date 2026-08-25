import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Any

import httpx


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_OUTPUT_PATH = Path(
    "demo_evaluation_report.json"
)

TERMINAL_STATUSES = {
    "SUCCESS",
    "FAILED",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the complete EvalFlow evaluation pipeline."
        )
    )

    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="EvalFlow API base URL.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path used to save the complete demo artifact.",
    )

    parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="Seconds between EvaluationRun polls.",
    )

    parser.add_argument(
        "--max-wait",
        type=float,
        default=180.0,
        help="Maximum seconds to wait for generation tasks.",
    )

    parser.add_argument(
        "--skip-llm-judge",
        action="store_true",
        help=(
            "Run only KeywordEvaluator and skip "
            "LLMJudgeEvaluator."
        ),
    )

    return parser.parse_args()


async def create_dataset(
    client: httpx.AsyncClient,
) -> int:
    response = await client.post(
        "/datasets",
        json={
            "name": (
                "portfolio_demo_"
                + datetime.now(timezone.utc).strftime(
                    "%Y%m%d_%H%M%S"
                )
            ),
            "description": (
                "EvalFlow portfolio end-to-end demo"
            ),
        },
    )

    response.raise_for_status()

    dataset_id = response.json()["dataset_id"]

    print(f"dataset_created dataset_id={dataset_id}")

    return dataset_id


async def create_cases(
    client: httpx.AsyncClient,
    dataset_id: int,
) -> None:
    cases = [
        {
            "prompt": "请用一句话解释 RAG 是什么。",
            "reference_answer": (
                "RAG 通过检索外部知识并将其作为上下文，"
                "辅助大语言模型生成回答。"
            ),
            "expected_keywords": [
                "检索",
                "外部知识",
                "生成",
            ],
        },
        {
            "prompt": (
                "请说明 HTTP 404 和 405 的区别。"
            ),
            "reference_answer": (
                "404 表示请求的资源不存在；"
                "405 表示资源存在，但当前 HTTP 方法"
                "不被该资源允许。"
            ),
            "expected_keywords": [
                "404",
                "405",
                "资源不存在",
                "方法",
            ],
        },
    ]

    for case in cases:
        response = await client.post(
            f"/datasets/{dataset_id}/cases",
            json=case,
        )

        response.raise_for_status()

        print(
            "case_created",
            f"case_id={response.json()['case_id']}",
        )


async def create_evaluation_run(
    client: httpx.AsyncClient,
    dataset_id: int,
) -> dict[str, Any]:
    response = await client.post(
        "/evaluation-runs",
        json={
            "dataset_id": dataset_id,
            "models": [
                "qwen3.7-flash",
                "glm-5.2",
            ],
        },
    )

    response.raise_for_status()

    evaluation_run = response.json()

    print(
        "evaluation_run_created",
        (
            "evaluation_run_id="
            f"{evaluation_run['evaluation_run_id']}"
        ),
        f"tasks={evaluation_run['total_tasks']}",
    )

    return evaluation_run


async def execute_and_wait(
    client: httpx.AsyncClient,
    evaluation_run_id: int,
    *,
    poll_interval: float,
    max_wait: float,
) -> dict[str, Any]:
    response = await client.post(
        f"/evaluation-runs/{evaluation_run_id}/run"
    )

    response.raise_for_status()

    print("evaluation_run_submitted")

    started_at = monotonic()

    while True:
        await asyncio.sleep(poll_interval)

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
            "generation_poll",
            f"success={success_count}",
            f"failed={failed_count}",
            f"processing={processing_count}",
        )

        if statuses and all(
            status in TERMINAL_STATUSES
            for status in statuses
        ):
            return evaluation_run

        if monotonic() - started_at > max_wait:
            raise TimeoutError(
                "EvaluationRun did not finish before "
                "the configured max wait time"
            )


async def evaluate_run(
    client: httpx.AsyncClient,
    evaluation_run_id: int,
    evaluator_name: str,
) -> dict[str, Any]:
    response = await client.post(
        f"/evaluation-runs/{evaluation_run_id}/evaluate",
        json={
            "evaluator": evaluator_name,
        },
    )

    response.raise_for_status()

    evaluation = response.json()

    print(
        "evaluation_completed",
        f"evaluator={evaluator_name}",
        (
            "evaluated_tasks="
            f"{evaluation['evaluated_tasks']}"
        ),
        (
            "skipped_tasks="
            f"{len(evaluation['skipped_tasks'])}"
        ),
    )

    return evaluation


async def get_report(
    client: httpx.AsyncClient,
    evaluation_run_id: int,
    evaluator_name: str,
) -> dict[str, Any]:
    response = await client.get(
        f"/evaluation-runs/{evaluation_run_id}/report",
        params={
            "evaluator": evaluator_name,
        },
    )

    response.raise_for_status()

    report = response.json()

    print_report_summary(report)

    return report


def print_report_summary(
    report: dict[str, Any],
) -> None:
    print(
        "\nreport",
        (
            f"{report['evaluator_name']}/"
            f"{report['evaluator_version']}"
        ),
    )

    for model in report["models"]:
        average_score = model["average_score"]

        score_text = (
            f"{average_score:.3f}"
            if average_score is not None
            else "N/A"
        )

        pass_rate = model["pass_rate"]

        pass_rate_text = (
            f"{pass_rate:.1%}"
            if pass_rate is not None
            else "N/A"
        )

        print(
            "model_summary",
            f"model={model['requested_model']}",
            f"score={score_text}",
            f"pass_rate={pass_rate_text}",
            (
                "latency_ms="
                f"{model['average_latency_ms']}"
            ),
            f"tokens={model['total_tokens']}",
        )

    print(
        "report_issues",
        f"bad_cases={len(report['bad_cases'])}",
        (
            "unassessed_cases="
            f"{len(report['unassessed_cases'])}"
        ),
    )


async def run_demo(
    args: argparse.Namespace,
) -> None:
    async with httpx.AsyncClient(
        base_url=args.base_url,
        timeout=300.0,
        trust_env=False,
    ) as client:
        health_response = await client.get("/health")
        health_response.raise_for_status()

        print("health_check ok")

        dataset_id = await create_dataset(client)

        await create_cases(
            client,
            dataset_id,
        )

        created_run = await create_evaluation_run(
            client,
            dataset_id,
        )

        evaluation_run_id = (
            created_run["evaluation_run_id"]
        )

        completed_run = await execute_and_wait(
            client,
            evaluation_run_id,
            poll_interval=args.poll_interval,
            max_wait=args.max_wait,
        )

        evaluations: dict[str, Any] = {}
        reports: dict[str, Any] = {}

        keyword_name = "keyword_match"

        evaluations[keyword_name] = await evaluate_run(
            client,
            evaluation_run_id,
            keyword_name,
        )

        reports[keyword_name] = await get_report(
            client,
            evaluation_run_id,
            keyword_name,
        )

        if not args.skip_llm_judge:
            judge_name = "llm_judge"

            evaluations[judge_name] = await evaluate_run(
                client,
                evaluation_run_id,
                judge_name,
            )

            reports[judge_name] = await get_report(
                client,
                evaluation_run_id,
                judge_name,
            )

        artifact = {
            "generated_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "dataset_id": dataset_id,
            "evaluation_run_id": evaluation_run_id,
            "generation": completed_run,
            "evaluations": evaluations,
            "reports": reports,
        }

        args.output.write_text(
            json.dumps(
                artifact,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        print(
            "\ndemo_completed",
            f"output={args.output.resolve()}",
        )


def main() -> None:
    args = parse_args()

    try:
        asyncio.run(run_demo(args))
    except httpx.HTTPError as exc:
        raise SystemExit(
            f"EvalFlow API request failed: {exc}"
        ) from exc
    except TimeoutError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()