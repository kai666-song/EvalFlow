import pytest
from app.evaluators.base import EvaluationContext
from app.evaluators.keyword import KeywordEvaluator


async def test_keyword_evaluator_scores_missing_keywords() -> None:
    evaluator = KeywordEvaluator()

    outcome = await evaluator.evaluate(
        EvaluationContext(
            question="什么是 RAG？",
            reference_answer=None,
            model_answer="RAG 会先检索相关资料。",
            metadata={
                "expected_keywords": [
                    "检索",
                    "外部知识",
                    "生成",
                ],
            },
        )
    )

    assert outcome.score == pytest.approx(1 / 3)
    assert outcome.passed is False
    assert outcome.reason == "缺少关键词：外部知识、生成"