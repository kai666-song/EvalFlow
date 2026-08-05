from time import perf_counter
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
)

from app.config import get_settings
from app.llm_models import LLMResult


MODEL_API_STYLE = {
    "qwen3.7-flash": "responses",
    "glm-5.2": "chat_completions",
}


async def _call_responses_api(
    client: AsyncOpenAI,
    prompt: str,
    model: str,
) -> LLMResult:
    """通过Responses API调用模型。"""

    start_time = perf_counter()

    response = await client.responses.create(
        model=model,
        input=prompt,
        reasoning={
            "effort": "medium",
        },
    )

    duration_ms = (
        perf_counter() - start_time
    ) * 1000

    text = response.output_text.strip()

    if not text:
        raise ValueError(
            "LLM returned an empty response"
        )

    usage_data = _to_dict(response.usage)

    input_tokens = int(
        usage_data.get("input_tokens") or 0
    )

    output_tokens = int(
        usage_data.get("output_tokens") or 0
    )

    total_tokens = int(
        usage_data.get("total_tokens") or 0
    )

    input_details = usage_data.get(
        "input_tokens_details"
    ) or {}

    if not isinstance(input_details, dict):
        input_details = {}

    cached_tokens = int(input_details.get("cached_tokens") or 0) 

    output_details = usage_data.get(
        "output_tokens_details"
    ) or {}

    if not isinstance(output_details, dict):
        output_details = {}

    reasoning_tokens = int(output_details.get("reasoning_tokens") or 0)

    return LLMResult(
        text=text,
        model=response.model or model,
        duration_ms=round(duration_ms, 2),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        reasoning_tokens=reasoning_tokens,
        cached_tokens=cached_tokens,
        total_tokens=total_tokens,
    )


async def _call_chat_completions_api(
    client: AsyncOpenAI,
    prompt: str,
    model: str,
) -> LLMResult:
    """通过Chat Completions API调用模型。"""

    start_time = perf_counter()

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        extra_body={
            "enable_thinking": True,
        },
    )

    duration_ms = (
        perf_counter() - start_time
    ) * 1000

    message = response.choices[0].message
    text = (message.content or "").strip()

    if not text:
        raise ValueError(
            "LLM returned an empty response"
        )

    usage_data = _to_dict(response.usage)
    
    input_tokens = int(
        usage_data.get("prompt_tokens") or 0
    )
    
    output_tokens = int(
        usage_data.get("completion_tokens") or 0
    )
    
    total_tokens = int(
        usage_data.get("total_tokens") or 0
    )
    
    prompt_details = usage_data.get(
        "prompt_tokens_details"
    ) or {}
    
    if not isinstance(prompt_details, dict):
        prompt_details = {}
    
    cached_tokens = int(prompt_details.get("cached_tokens") or 0) 
    
    completion_details = usage_data.get(
        "completion_tokens_details"
    ) or {}
    
    if not isinstance(completion_details, dict):
        completion_details = {}

    reasoning_tokens = int(
        completion_details.get("reasoning_tokens") or 0
    )

    return LLMResult(
        text=text,
        model=response.model or model,
        duration_ms=round(duration_ms, 2),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        reasoning_tokens=reasoning_tokens,
        cached_tokens=cached_tokens,
        total_tokens=total_tokens,
    )


async def process_prompt(
    prompt: str,
    model: str | None = None,
) -> LLMResult:
    """根据模型类型选择兼容接口并返回统一结果。"""

    settings = get_settings()
    selected_model = model or settings.llm_model

    api_style = MODEL_API_STYLE.get(
        selected_model
    )

    if api_style is None:
        raise ValueError(
            f"Unsupported model: {selected_model}"
        )

    try:
        async with AsyncOpenAI(
            api_key=(
                settings
                .dashscope_api_key
                .get_secret_value()
            ),
            base_url=settings.llm_base_url,
            timeout=settings.llm_timeout_seconds,
        ) as client:
            if api_style == "responses":
                return await _call_responses_api(
                    client=client,
                    prompt=prompt,
                    model=selected_model,
                )

            return await _call_chat_completions_api(
                client=client,
                prompt=prompt,
                model=selected_model,
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
            f"LLM service returned HTTP "
            f"{exc.status_code}"
        ) from exc

def _to_dict(value: Any) -> dict[str, Any]:
    """将openai SDK响应对象安全转换为普通字典。"""

    if value is None:
        return {}

    if isinstance(value, dict):
         return value

    if hasattr(value, "model_dump"):
        data = value.model_dump()

        if isinstance(data, dict):
            return data

    return {}