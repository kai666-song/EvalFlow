from datetime import datetime, timezone
from uuid import uuid4
from time import perf_counter
from contextlib import asynccontextmanager
from typing import Annotated

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status

from app.models import TaskCreate, TaskResponse, TaskStatus
from app.processor import process_prompt
from app.logger import get_logger   
from app.database import AsyncSessionFactory, engine, get_session, init_database
from app.db_models import TaskRecord

logger = get_logger()
async def recover_interrupted_tasks() -> int:
    """将服务重启前遗留的处理中任务标记为失败。"""

    async with AsyncSessionFactory() as session:
        statement=(
            update(TaskRecord)
            .where(
                TaskRecord.status == TaskStatus.PROCESSING.value
            )
            .values(
                status=TaskStatus.FAILED.value,
                result=None,
                error="Task interrupted by service restart"
            )
        )

    result = await session.execute(statement)
    await session.commit()

    return result.rowcount or 0

@asynccontextmanager
async def lifespan(app: FastAPI):
    """管理应用启动和关闭期间的资源。"""

    await init_database()

    logger.info("database_initialized")
    recovered_count = await recover_interrupted_tasks()

    logger.info(
        "interrupted_tasks_recovered count=%s",
        recovered_count,
    )

    try:
        yield
    finally:
        await engine.dispose()
        logger.info("databse_engine_disposed")

app = FastAPI(
    title="EvalFlow",
    description="AI任务与模型评测平台",
    version="0.1.0",
    lifespan=lifespan,
)

SessionDep = Annotated[AsyncSession, Depends(get_session)]

async def execute_task(task_id: str) -> None:
    """在独立数据库会话中执行任务并更新状态。"""

    start_time = perf_counter()

    async with AsyncSessionFactory() as session:
        task = await session.get(TaskRecord, task_id)

        if task is None:
            logger.error(
                "task_execute_not_found task_id=%s",
                task_id,
            )
            return

        logger.info(
            "task_started task_id=%s prompt=%r",
            task.task_id,
            task.prompt,
        )

        try:
            result = await process_prompt(task.prompt)

            task.result = result
            task.status = TaskStatus.SUCCESS.value
            task.error = None

            # 真正将SUCCESS和result写入数据库。
            await session.commit()

            duration_ms = (perf_counter() - start_time) * 1000

            logger.info(
                "task_succeeded task_id=%s "
                "persisted_status=%s duration_ms=%.2f",
                task.task_id,
                task.status,
                duration_ms,
            )

        except ValueError as exc:
            task.status = TaskStatus.FAILED.value
            task.result = None
            task.error = str(exc)

            await session.commit()

            duration_ms = (perf_counter() - start_time) * 1000

            logger.warning(
                "task_failed task_id=%s error_type=%s "
                "duration_ms=%.2f error=%s",
                task.task_id,
                type(exc).__name__,
                duration_ms,
                exc,
            )

        except Exception as exc:
            # 撤销当前会话中尚未提交的修改。
            await session.rollback()

            # rollback后重新查询，确保对象重新属于当前Session。
            task = await session.get(TaskRecord, task_id)

            if task is not None:
                task.status = TaskStatus.FAILED.value
                task.result = None
                task.error = f"Unexpected error: {exc}"

                await session.commit()

            duration_ms = (perf_counter() - start_time) * 1000

            logger.exception(
                "task_failed_unexpected task_id=%s "
                "error_type=%s duration_ms=%.2f",
                task_id,
                type(exc).__name__,
                duration_ms,
            )
    

@app.get("/health")
async def health_check() -> dict[str, str]:
    """检查服务是否正常运行。"""
    return {"status": "ok"}


@app.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_task(payload: TaskCreate, session: SessionDep) -> TaskResponse:
    """创建一个新的AI处理任务。"""

    task = TaskRecord(
        task_id=str(uuid4()),
        prompt=payload.prompt,
        status=TaskStatus.PENDING.value,
        result=None,
        error=None,
        created_at=datetime.now(timezone.utc),
    )

    session.add(task)
    await session.commit()
    await session.refresh(task)

    logger.info(
        "task_created task_id=%s status=%s",
        task.task_id,
        task.status
    )

    return TaskResponse.model_validate(task)


@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, session: SessionDep) -> TaskResponse:
    """根据任务ID从数据库查询任务。"""

    task = await session.get(TaskRecord, task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    return TaskResponse.model_validate(task)

@app.post("/tasks/{task_id}/run", response_model=TaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_task(task_id: str, background_tasks: BackgroundTasks, session: SessionDep) -> TaskResponse:
    """将数据库中的任务提交到后台执行。"""

    task = await session.get(TaskRecord, task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    if task.status == TaskStatus.PROCESSING.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task is already processing",
        )

    task.status = TaskStatus.PROCESSING.value
    task.result = None
    task.error = None

    await session.commit()
    await session.refresh(task)

    logger.info(
        "task_submitted task_id=%s status=%s",
        task.task_id,
        task.status
    )

    background_tasks.add_task(execute_task, task.task_id)

    return TaskResponse.model_validate(task)