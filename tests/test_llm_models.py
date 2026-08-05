import pytest
from pydantic import ValidationError

from app.llm_models import LLMResult


def test_llm_result_preserves_reasoning_tokens() -> None:
    """推理Token应该被正确保存。"""

    result = LLMResult(
        text="测试回答",
        model="test-model",
        duration_ms=100.0,
        input_tokens=10,
        output_tokens=30,
        reasoning_tokens=20,
        cached_tokens=0,
        total_tokens=40,
    )

    assert result.reasoning_tokens == 20

    dumped = result.model_dump()

    assert dumped["reasoning_tokens"] == 20

    # 这里故意检查错误拼写不存在
    assert "resoning_tokens" not in dumped


def test_llm_result_rejects_misspelled_field() -> None:
    """拼错字段名时不应被静默忽略。"""

    payload = {
        "text": "测试回答",
        "model": "test-model",
        "duration_ms": 100.0,
        "input_tokens": 10,
        "output_tokens": 30,

        # 这里故意使用错误拼写
        "resoning_tokens": 20,

        "cached_tokens": 0,
        "total_tokens": 40,
    }

    with pytest.raises(ValidationError):
        LLMResult.model_validate(payload)