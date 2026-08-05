import asyncio
import json
import sys

from app.processor import process_prompt


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


async def main() -> None:
    models = [
        "qwen3.7-flash",
        "glm-5.2",
    ]

    prompt = (
        "请使用中文，并用不超过三句话解释"
        "RAG相比直接调用大语言模型有什么优势。"
    )

    for model in models:
        print(f"\n========== {model} ==========")

        result = await process_prompt(
            prompt=prompt,
            model=model,
        )

        print(
            json.dumps(
                result.model_dump(),
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    asyncio.run(main())