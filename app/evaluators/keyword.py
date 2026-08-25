from app.evaluators.base import (
    BaseEvaluator,
    EvaluationContext,
    EvaluationOutcome,
)


class KeywordEvaluator(BaseEvaluator):
    """检查模型答案是否覆盖 Case 中声明的关键词。"""

    name = "keyword_match"
    version = "1.0"

    def get_skip_reason(
        self,
        context: EvaluationContext,
    ) -> str | None:
        raw_keywords = context.metadata.get(
            "expected_keywords",
            [],
        )

        if not isinstance(raw_keywords, list):
            return (
                "KeywordEvaluator requires "
                "expected_keywords as a list"
            )

        if not raw_keywords:
            return (
                "KeywordEvaluator requires at least "
                "one expected keyword"
            )

        if not all(
            isinstance(keyword, str) and keyword.strip()
            for keyword in raw_keywords
        ):
            return (
                "KeywordEvaluator received an invalid keyword"
            )

        return None

    async def evaluate(
        self,
        context: EvaluationContext,
    ) -> EvaluationOutcome:
        skip_reason = self.get_skip_reason(context)

        if skip_reason is not None:
            raise ValueError(skip_reason)

        raw_keywords = context.metadata["expected_keywords"]

        normalized_answer = self._normalize(
            context.model_answer
        )

        matched_keywords = [
            keyword
            for keyword in raw_keywords
            if self._normalize(keyword) in normalized_answer
        ]

        missing_keywords = [
            keyword
            for keyword in raw_keywords
            if keyword not in matched_keywords
        ]

        score = len(matched_keywords) / len(raw_keywords)
        passed = not missing_keywords

        reason = (
            "所有关键词均已命中"
            if passed
            else "缺少关键词：" + "、".join(missing_keywords)
        )

        return EvaluationOutcome(
            score=score,
            passed=passed,
            reason=reason,
        )

    @staticmethod
    def _normalize(text: str) -> str:
        """忽略大小写和空白差异，保留可解释的子串匹配。"""

        return "".join(text.casefold().split())