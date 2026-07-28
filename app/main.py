from datetime import datetime, timezone
from uuid import uuid4
from time import perf_counter

from fastapi import BackgroundTasks, FastAPI, HTTPException, status

from app.models import TaskCreate, TaskResponse, TaskStatus
from app.processor import process_prompt
from app.logger import get_logger   

app = FastAPI(
    title="EvalFlow",
    description="AI任务与模型评测平台",
    version="0.1.0"
)

logger = get_logger()

# 目前暂时使用内存字典保存任务。
# 程序重启后数据会消失，后面将替换为数据库。
tasks: dict[str, TaskResponse] = {}

async def execute_task(task: TaskResponse) -> None:
    """在后台执行任务，更新任务状态。"""

    start_time = perf_counter()

    logger.info(
        "task_started task_id=%s prompt=%r",
        task.task_id,
        task.prompt,
    )

    try:
        task.result = await process_prompt(task.prompt)
        task.status = TaskStatus.SUCCESS

        duration_ms = (perf_counter() - start_time) * 1000

        logger.info(
            "task_succeeded task_id=%s duration_ms=%.2f",
            task.task_id,
            duration_ms,
        )

    except ValueError as exc:
        task.status = TaskStatus.FAILED
        task.result = None
        task.error = str(exc)

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
        task.status = TaskStatus.FAILED
        task.result = None
        task.error = f"Unexpected error: {exc}"

        duration_ms = (perf_counter() - start_time) * 1000

        logger.exception(
            "task_failed_unexpected task_id=%s "
            "error_type=%s duration_ms=%.2f",
            task.task_id,
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
async def create_task(payload: TaskCreate) -> TaskResponse:
    """创建一个新的AI处理任务。"""

    task = TaskResponse(
        task_id=str(uuid4()),
        prompt=payload.prompt,
        status=TaskStatus.PENDING,
        result=None,
        error=None,
        created_at=datetime.now(timezone.utc),
    )

    tasks[task.task_id] = task

    logger.info(
        "task_created task_id=%s status=%s",
        task.task_id,
        task.status
    )

    return task

@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str) -> TaskResponse:
    """根据任务ID查询任务。"""

    task = tasks.get(task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    return task

@app.post("/tasks/{task_id}/run", response_model=TaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_task(task_id: str, background_tasks: BackgroundTasks) -> TaskResponse:
    """提交任务到后台执行。"""

    task = tasks.get(task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    if task.status == TaskStatus.PROCESSING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task is already processing",
        )

    task.status = TaskStatus.PROCESSING
    task.result = None
    task.error = None

    logger.info(
        "task_submitted task_id=%s status=%s",
        task.task_id,
        task.status
    )

    background_tasks.add_task(execute_task, task)

    return task