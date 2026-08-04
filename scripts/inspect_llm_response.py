import asyncio
import json
import sys
from time import perf_counter

from openai import AsyncOpenAI

from app.config import get_settings


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


async def main() -> None:
    """检查百炼Responses API返回的模型与Token字段。"""

    settings = get_settings()

    async with AsyncOpenAI(
        api_key=settings.dashscope_api_key.get_secret_value(),
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout_seconds,
    ) as client:
        start_time = perf_counter()

        response = await client.responses.create(
            model=settings.llm_model,
            input="请只回复四个字：测试成功",
        )

        duration_ms = (perf_counter() - start_time) * 1000

    usage = getattr(response, "usage", None)

    if usage is not None and hasattr(usage, "model_dump"):
        usage_data = usage.model_dump()
    else:
        usage_data = None

    result = {
        "response_type": type(response).__name__,
        "requested_model": settings.llm_model,
        "returned_model": getattr(response, "model", None),
        "duration_ms": round(duration_ms, 2),
        "usage": usage_data,
        "output_text": response.output_text,
    }

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())