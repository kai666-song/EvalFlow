from pydantic import BaseModel, ConfigDict, Field

class LLMResult(BaseModel):
    """一次大模型调用的文本结果和运行指标。"""
    model_config = ConfigDict(
        extra="forbid",
    )
    
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

    reasoning_tokens: int = Field(
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