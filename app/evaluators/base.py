from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field


class EvaluationContext(BaseModel):
    """提供给所有 Evaluator 的统一评测上下文。"""

    model_config = ConfigDict(frozen=True)

    question: str
    reference_answer: str | None = None
    model_answer: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluationOutcome(BaseModel):
    """Evaluator 的统一内存输出，随后由 service 持久化。"""

    score: float = Field(ge=0, le=1)
    passed: bool
    reason: str | None = None


class BaseEvaluator(ABC):
    """所有自动化 Evaluator 的扩展点。"""

    name: ClassVar[str]
    version: ClassVar[str]

    def get_skip_reason(
        self,
        context: EvaluationContext,
    ) -> str | None:
        """返回不可评测原因；None 表示可以评测。"""

        return None

    @property
    def config(self) -> dict[str, Any] | None:
        """返回应随 Result 持久化的 Evaluator 运行配置。"""

        return None

    @abstractmethod
    async def evaluate(
        self,
        context: EvaluationContext,
    ) -> EvaluationOutcome:
        """根据上下文生成标准化评分结果。"""