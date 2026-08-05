import asyncio
import sys
import json
from time import perf_counter

from openai import AsyncOpenAI

from app.config import get_settings

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

async def main() -> None:
    """使用 Chat Completions 接口直接验证GLM模型。"""

    settings = get_settings()

    async with AsyncOpenAI(
        api_key=(
            settings
            .dashscope_api_key
            .get_secret_value()
        ),
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout_seconds,
    ) as client:
        start_time = perf_counter()

        response = await client.chat.completions.create(
            model="glm-5.2",
            messages=[
                {
                    "role": "user",
                    "content": (
                        "请使用中文，并用不超过三句话解释"
                        "RAG相比直接调用大语言模型有什么优势。"
                    ),
                }
            ],
            extra_body={
                "enable_thinking": True,
            },
        )

        duration_ms = (perf_counter() - start_time)*1000

    message = response.choices[0].message
    usage = response.usage

    usage_data = (
        usage.model_dump() if usage is not None else None
    )

    result = {
        "model": response.model,
        "duration_ms": round(duration_ms, 2),
        "content": message.content,
        "reasoning_content": getattr(
            message,
            "reasoning_content",
            None,
        ),
        "usage": usage_data,
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