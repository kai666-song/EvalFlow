import pytest

import app.evaluators.llm_judge as llm_judge_module
from app.evaluators.base import EvaluationContext
from app.evaluators.llm_judge import LLMJudgeEvaluator
from app.llm_models import LLMResult


async def fake_process_prompt(
    prompt: str,
    model: str | None = None,
) -> LLMResult:
    return LLMResult(
        text=(
            '{"score": 85, '
            '"reason": "回答总体正确，但略缺少细节。"}'
        ),
        model="judge-test-model",
        duration_ms=10.0,
        input_tokens=10,
        output_tokens=20,
        reasoning_tokens=0,
        cached_tokens=0,
        total_tokens=30,
    )


async def test_llm_judge_returns_normalized_outcome(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        llm_judge_module,
        "process_prompt",
        fake_process_prompt,
    )

    evaluator = LLMJudgeEvaluator(
        model="qwen3.7-flash",
    )

    outcome = await evaluator.evaluate(
        EvaluationContext(
            question="什么是 RAG？",
            reference_answer=(
                "RAG 使用检索到的外部知识"
                "辅助模型生成回答。"
            ),
            model_answer=(
                "RAG 会先检索外部知识，"
                "再让模型据此生成回答。"
            ),
        )
    )

    assert outcome.score == 0.85
    assert outcome.passed is True
    assert outcome.reason == "回答总体正确，但略缺少细节。"
    assert evaluator.config == {
        "judge_model": "judge-test-model",
        "prompt_version": "1.0",
        "passing_score": 70,
    }


async def test_llm_judge_rejects_invalid_json(
    monkeypatch,
) -> None:
    async def fake_invalid_process_prompt(
        prompt: str,
        model: str | None = None,
    ) -> LLMResult:
        return LLMResult(
            text="不是 JSON",
            model="judge-test-model",
            duration_ms=10.0,
            input_tokens=10,
            output_tokens=20,
            reasoning_tokens=0,
            cached_tokens=0,
            total_tokens=30,
        )

    monkeypatch.setattr(
        llm_judge_module,
        "process_prompt",
        fake_invalid_process_prompt,
    )

    evaluator = LLMJudgeEvaluator()

    with pytest.raises(
        ValueError,
        match="did not return valid JSON",
    ):
        await evaluator.evaluate(
            EvaluationContext(
                question="测试问题",
                reference_answer="参考答案",
                model_answer="模型回答",
            )
        )