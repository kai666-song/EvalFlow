from time import perf_counter

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from app.config import get_settings
from app.llm_models import LLMResult

async def process_prompt(prompt: str) -> LLMResult:
    """调用真实大模型，返回文本和调用指标。"""

    settings = get_settings()
    start_time = perf_counter()

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

    duration_ms = (perf_counter() - start_time) * 1000
    text = response.output_text.strip()

    if not text:
        raise ValueError(
            "LLM returned an empty response"
        )

    usage = response.usage

    input_tokens = 0
    output_tokens = 0
    reasoning_tokens = 0
    cached_tokens = 0
    total_tokens = 0

    if usage is not None:
        input_tokens = usage.input_tokens or 0
        output_tokens = usage.output_tokens or 0
        total_tokens = usage.total_tokens or 0

        input_details = usage.input_tokens_details

        if input_details is not None:
            cached_tokens = input_details.cached_tokens or 0

        output_details = usage.output_tokens_details

        if output_details is not None:
            reasoning_tokens = output_details.reasoning_tokens or 0

    return LLMResult(
        text=text,
        model=response.model or settings.llm_model,
        duration_ms=round(duration_ms, 2),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        resoning_tokens=reasoning_tokens,
        cached_tokens=cached_tokens,
        total_tokens=total_tokens,
    )