from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from app.config import get_settings

async def process_prompt(prompt: str) -> str:
    """调用真实大模型处理Prompt并返回文本结果。"""

    settings = get_settings()

    try:
        async with AsyncOpenAI(
            api_key=settings.dashscope_api_key.get_secret_value(),
            base_url=settings.llm_base_url,
            timeout=settings.llm_timeout_seconds,
        ) as client:
            response = await client.responses.create(
                model=settings.llm_model,
                input=prompt,
            )

    except APITimeoutError as exc:
        raise ValueError(
            "LLM request timed out"
        ) from exc

    except APIConnectionError as exc:
        raise ValueError(
            "Unable to connect to LLM service"
        ) from exc

    except APIStatusError as exc:
        raise ValueError(
            f"LLM service returned HTP {exc.status_code}"
        ) from exc

    result = response.output_text.strip()

    if not result:
        raise ValueError(
            "LLM returned an empty response"
        )

    return result