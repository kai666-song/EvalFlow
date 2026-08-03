from datetime import datetime, timezone
from uuid import uuid4

from httpx import AsyncClient

import app.main as main_module
from app.db_models import TaskRecord
from app.models import TaskStatus


async def test_recover_interrupted_tasks_marks_processing_as_failed(
    client: AsyncClient,
) -> None:
    """服务恢复时，应将PROCESSING任务标记为FAILED。"""

    # client fixture在这里负责：
    # 1. 创建内存测试数据库；
    # 2. 将AsyncSessionFactory替换为测试Session工厂。
    processing_task_id = str(uuid4())
    pending_task_id = str(uuid4())

    async with main_module.AsyncSessionFactory() as session:
        processing_task = TaskRecord(
            task_id=processing_task_id,
            prompt="服务中断前正在执行的任务",
            status=TaskStatus.PROCESSING.value,
            result="尚未完成的临时结果",
            error=None,
            created_at=datetime.now(timezone.utc),
        )

        pending_task = TaskRecord(
            task_id=pending_task_id,
            prompt="尚未开始执行的任务",
            status=TaskStatus.PENDING.value,
            result=None,
            error=None,
            created_at=datetime.now(timezone.utc),
        )

        session.add_all(
            [
                processing_task,
                pending_task,
            ]
        )

        await session.commit()

    recovered_count = await main_module.recover_interrupted_tasks()

    assert recovered_count == 1

    async with main_module.AsyncSessionFactory() as session:
        recovered_task = await session.get(
            TaskRecord,
            processing_task_id,
        )

        unchanged_task = await session.get(
            TaskRecord,
            pending_task_id,
        )

    assert recovered_task is not None
    assert recovered_task.status == TaskStatus.FAILED.value
    assert recovered_task.result is None
    assert recovered_task.error == (
        "Task interrupted by service restart"
    )

    assert unchanged_task is not None
    assert unchanged_task.status == TaskStatus.PENDING.value
    assert unchanged_task.result is None
    assert unchanged_task.error is None