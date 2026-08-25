from app.evaluators.base import BaseEvaluator
from app.evaluators.keyword import KeywordEvaluator
from app.evaluators.llm_judge import LLMJudgeEvaluator
from app.models import EvaluatorType


def create_evaluator(
    evaluator_type: EvaluatorType,
) -> BaseEvaluator:
    """根据公开 API 类型创建受支持的 Evaluator。"""

    if evaluator_type == EvaluatorType.KEYWORD_MATCH:
        return KeywordEvaluator()

    if evaluator_type == EvaluatorType.LLM_JUDGE:
        return LLMJudgeEvaluator()

    raise ValueError(
        f"Unsupported evaluator: {evaluator_type}"
    )