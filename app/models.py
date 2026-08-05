from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field
from enum import StrEnum


class SupportedModel(StrEnum):
    """当前平台允许调用的大模型。"""

    QWEN_3_7_FLASH = "qwen3.7-flash"
    GLM_5_2 = "glm-5.2"


class TaskStatus(StrEnum):
    """AI任务可能处于的状态"""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class TaskCreate(BaseModel):
    prompt: str = Field(
        min_length=1,
        max_length=2000,
    )

    model: SupportedModel = SupportedModel.QWEN_3_7_FLASH

class TaskResponse(BaseModel):
    """服务器返回给客户端的完整任务信息。"""

    model_config = ConfigDict(from_attributes=True)

    task_id: str
    prompt: str
    status: TaskStatus
    model_name: str | None=None
    llm_duration_ms: float | None=None

    input_tokens: int | None=None
    output_tokens: int | None=None
    reasoning_tokens: int | None=None
    cached_tokens: int | None=None
    total_tokens: int | None=None

    result: str | None=None
    error: str | None=None
    created_at: datetime

    requested_model: SupportedModel | None=None

class TaskListResponse(BaseModel):
    """任务列表响应。"""

    items: list[TaskResponse]
    total: int
    limit: int
    offset: int
