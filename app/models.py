from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, Field

class TaskStatus(StrEnum):
    """AI任务可能处于的状态"""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class TaskCreate(BaseModel):
    """客户端创建任务时需要提交的数据。"""

    prompt: str = Field(
        min_length=1,
        max_length=2000,
        description="需要模型处理的文本指令。",
    )

class TaskResponse(BaseModel):
    """服务器返回给客户端的完整任务信息。"""

    task_id: str
    prompt: str
    status: TaskStatus
    result: str | None=None
    error: str | None=None
    created_at: datetime