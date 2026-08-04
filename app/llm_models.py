from pydantic import BaseModel, Field

class LLMResult(BaseModel):
    """一次大模型调用的文本结果和运行指标。"""

    text: str

    model: str

    duration_ms: float = Field(
        ge=0,
    )

    input_tokens: int = Field(
        default=0,
        ge=0,
    )

    output_tokens: int = Field(
        default=0,
        ge=0,
    )

    resoning_tokens: int = Field(
        default=0,
        ge=0,
    )

    cached_tokens: int = Field(
        default=0,
        ge=0,
    )

    total_tokens: int = Field(
        default=0,
        ge=0,
    )