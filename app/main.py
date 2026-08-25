import asyncio

from datetime import datetime, timezone
from uuid import uuid4
from time import perf_counter
from contextlib import asynccontextmanager
from typing import Annotated

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, update

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, status

from app.models import ComparisonCreate, ComparisonResponse, TaskCreate, TaskListResponse, TaskResponse, TaskStatus, EvaluationDatasetCreate, EvaluationDatasetResponse, EvaluationCaseCreate, EvaluationCaseResponse, EvaluationDatasetDetailResponse, EvaluationRunComparisonResponse, EvaluationRunCreate, EvaluationRunResponse, EvaluationResultResponse,EvaluationRunEvaluateResponse, SkippedEvaluationTaskResponse, EvaluationRunEvaluateRequest, EvaluatorType, EvaluationRunReportResponse
from app.processor import process_prompt
from app.logger import get_logger   
from app.database import AsyncSessionFactory, engine, get_session, init_database
from app.db_models import ComparisonRecord, TaskRecord, EvaluationDatasetRecord , EvaluationCaseRecord, EvaluationRunRecord, EvaluationResultRecord
from app.evaluation_service import (
    EvaluationRunNotReadyError,
    evaluate_evaluation_run,
)
from app.evaluators.factory import create_evaluator
from app.report_service import EvaluationReportNotReadyError, build_evaluation_run_report


def _build_task_record(
    *,
    prompt: str,
    requested_model: str,
    comparison_id: int | None=None,
) -> TaskRecord:
    """构造一条尚未执行的模型任务记录。"""

    return TaskRecord(
        task_id=str(uuid4()),
        prompt=prompt,
        status=TaskStatus.PENDING.value,
        requested_model=requested_model,
        comparison_id=comparison_id,
        model_name=None,
        llm_duration_ms=None,
        input_tokens=None,
        output_tokens=None,
        reasoning_tokens=None,
        cached_tokens=None,
        total_tokens=None,
        result=None,
        error=None,
        created_at=datetime.now(timezone.utc),
    )

logger = get_logger()
async def recover_interrupted_tasks() -> int:
    """将服务重启前遗留的处理中任务标记为失败。"""

    async with AsyncSessionFactory() as session:
        statement = (
            update(TaskRecord)
            .where(
                TaskRecord.status == TaskStatus.PROCESSING.value
            )
            .values(
                status=TaskStatus.FAILED.value,
                result=None,
                error="Task interrupted by service restart",
                model_name=None,
                llm_duration_ms=None,
                input_tokens=None,
                output_tokens=None,
                reasoning_tokens=None,
                cached_tokens=None,
                total_tokens=None,
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
        logger.info("database_engine_disposed")

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
            llm_result = await process_prompt(task.prompt, model=task.requested_model)

            task.result = llm_result.text
            task.status = TaskStatus.SUCCESS.value
            task.error = None

            task.model_name = llm_result.model
            task.llm_duration_ms = llm_result.duration_ms
            task.input_tokens = llm_result.input_tokens
            task.output_tokens = llm_result.output_tokens
            task.reasoning_tokens = llm_result.reasoning_tokens
            task.cached_tokens = llm_result.cached_tokens
            task.total_tokens = llm_result.total_tokens

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

            task.model_name = None
            task.llm_duration_ms = None
            task.input_tokens = None
            task.reasoning_tokens = None
            task.output_tokens = None
            task.cached_tokens = None
            task.total_tokens = None

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

                task.model_name = None
                task.llm_duration_ms = None
                task.input_tokens = None
                task.output_tokens = None
                task.reasoning_tokens = None
                task.cached_tokens = None
                task.total_tokens = None

                await session.commit()

            duration_ms = (perf_counter() - start_time) * 1000

            logger.exception(
                "task_failed_unexpected task_id=%s "
                "error_type=%s duration_ms=%.2f",
                task_id,
                type(exc).__name__,
                duration_ms,
            )

async def execute_comparison_tasks(task_ids: list[str]) -> None:
    """并发执行一次模型对比中的所有子任务。"""

    await asyncio.gather(
        *(execute_task(task_id) for task_id in task_ids)
    )    


async def execute_evaluation_run_tasks(
    task_ids: list[str],
    max_concurrency: int = 5,
) -> None:
    """以受控并发方式执行整批 Evaluation Task。"""

    semaphore = asyncio.Semaphore(max_concurrency)

    async def execute_with_limit(
        task_id: str,
    ) -> None:
        async with semaphore:
            await execute_task(task_id)

    await asyncio.gather(
        *(
            execute_with_limit(task_id)
            for task_id in task_ids
        )
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    """检查服务是否正常运行。"""
    return {"status": "ok"}


@app.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_task(
    payload: TaskCreate,
    session: AsyncSession = Depends(get_session),
) -> TaskResponse:
    """创建一条待执行的大模型任务。"""

    task = _build_task_record(
        prompt=payload.prompt,
        requested_model=payload.model.value,
    )

    session.add(task)
    await session.commit()
    await session.refresh(task)

    logger.info(
        "task_created task_id=%s status=%s",
        task.task_id,
        task.status,
    )

    return TaskResponse.model_validate(task)


@app.post(
        "/datasets",
        response_model=EvaluationDatasetResponse,
        status_code=status.HTTP_201_CREATED,
)
async def create_dataset(payload: EvaluationDatasetCreate, session: SessionDep) -> EvaluationDatasetResponse:
    """创建一份评测数据集。"""

    dataset = EvaluationDatasetRecord(name=payload.name, description=payload.description, created_at=datetime.now(timezone.utc))

    session.add(dataset)

    await session.commit()
    await session.refresh(dataset)

    return EvaluationDatasetResponse(dataset_id=dataset.id, name=dataset.name, description=dataset.description, created_at=dataset.created_at)


@app.post(
    "/datasets/{dataset_id}/cases",
    response_model=EvaluationCaseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_evaluation_case(
    dataset_id: int,
    payload: EvaluationCaseCreate,
    session: SessionDep,
) -> EvaluationCaseResponse:
    """向指定评测数据集中新增一条评测样本。"""

    dataset = await session.get(
        EvaluationDatasetRecord,
        dataset_id,
    )

    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found",
        )

    evaluation_case = EvaluationCaseRecord(
        dataset_id=dataset_id,
        prompt=payload.prompt,
        reference_answer=payload.reference_answer,
        created_at=datetime.now(timezone.utc),
        expected_keywords=payload.expected_keywords,
    )

    session.add(evaluation_case)

    await session.commit()
    await session.refresh(evaluation_case)

    return EvaluationCaseResponse(
        case_id=evaluation_case.id,
        dataset_id=evaluation_case.dataset_id,
        prompt=evaluation_case.prompt,
        reference_answer=evaluation_case.reference_answer,
        expected_keywords=(
            evaluation_case.expected_keywords or []
        ),
        created_at=evaluation_case.created_at,
    )


@app.get(
    "/datasets/{dataset_id}",
    response_model=EvaluationDatasetDetailResponse,
)
async def get_dataset(
    dataset_id: int,
    session: SessionDep,
) -> EvaluationDatasetDetailResponse:
    """查询数据集及其全部评测样本。"""

    dataset = await session.get(
        EvaluationDatasetRecord,
        dataset_id,
    )

    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found",
        )

    result = await session.execute(
        select(EvaluationCaseRecord)
        .where(
            EvaluationCaseRecord.dataset_id == dataset_id
        )
        .order_by(EvaluationCaseRecord.id.asc())
    )

    cases = result.scalars().all()

    return EvaluationDatasetDetailResponse(
        dataset_id=dataset.id,
        name=dataset.name,
        description=dataset.description,
        created_at=dataset.created_at,
        total_cases=len(cases),
        cases=[
            EvaluationCaseResponse(
                case_id=evaluation_case.id,
                dataset_id=evaluation_case.dataset_id,
                prompt=evaluation_case.prompt,
                reference_answer=evaluation_case.reference_answer,
                created_at=evaluation_case.created_at,
                expected_keywords=evaluation_case.expected_keywords or [],
            )
            for evaluation_case in cases
        ],
    )


@app.post(
    "/evaluation-runs",
    response_model=EvaluationRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_evaluation_run(
    payload: EvaluationRunCreate,
    session: SessionDep,
) -> EvaluationRunResponse:
    """基于整个 Dataset 创建一次批量模型评测。"""

    # 1. 确认 Dataset 存在
    dataset = await session.get(
        EvaluationDatasetRecord,
        payload.dataset_id,
    )

    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found",
        )

    # 2. 查询 Dataset 中的全部 Case
    result = await session.execute(
        select(EvaluationCaseRecord)
        .where(
            EvaluationCaseRecord.dataset_id
            == payload.dataset_id
        )
        .order_by(EvaluationCaseRecord.id.asc())
    )

    cases = result.scalars().all()

    if not cases:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dataset has no cases",
        )

    # 3. 创建 EvaluationRun
    evaluation_run = EvaluationRunRecord(
        dataset_id=payload.dataset_id,
        created_at=datetime.now(timezone.utc),
    )

    session.add(evaluation_run)

    # 拿到数据库生成的 evaluation_run.id
    await session.flush()

    comparison_records = []

    # 4. 每条 Case 创建一个 Comparison
    for evaluation_case in cases:
        comparison = ComparisonRecord(
            prompt=evaluation_case.prompt,
            evaluation_run_id=evaluation_run.id,
            evaluation_case_id=evaluation_case.id,
        )

        session.add(comparison)

        # 拿到 comparison.id
        await session.flush()

        # 5. 每个模型创建一个 Task
        tasks = [
            _build_task_record(
                prompt=evaluation_case.prompt,
                requested_model=model.value,
                comparison_id=comparison.id,
            )
            for model in payload.models
        ]

        session.add_all(tasks)

        comparison_records.append(
            (
                evaluation_case,
                comparison,
                tasks,
            )
        )

    # 6. 整批数据统一提交
    await session.commit()

    # 7. 刷新数据库对象
    await session.refresh(evaluation_run)

    for _, comparison, tasks in comparison_records:
        await session.refresh(comparison)

        for task in tasks:
            await session.refresh(task)

    total_tasks = sum(
        len(tasks)
        for _, _, tasks in comparison_records
    )

    # 8. 构造响应
    return EvaluationRunResponse(
        evaluation_run_id=evaluation_run.id,
        dataset_id=evaluation_run.dataset_id,
        total_cases=len(cases),
        total_comparisons=len(comparison_records),
        total_tasks=total_tasks,
        comparisons=[
            EvaluationRunComparisonResponse(
                evaluation_case_id=evaluation_case.id,
                comparison_id=comparison.id,
                prompt=comparison.prompt,
                total=len(tasks),
                tasks=[
                    TaskResponse.model_validate(task)
                    for task in tasks
                ],
            )
            for evaluation_case, comparison, tasks
            in comparison_records
        ],
    )


@app.get(
    "/evaluation-runs/{evaluation_run_id}",
    response_model=EvaluationRunResponse,
)
async def get_evaluation_run(
    evaluation_run_id: int,
    session: SessionDep,
) -> EvaluationRunResponse:
    """查询一次批量评测及其所有 Comparison 和 Task。"""

    evaluation_run = await session.get(
        EvaluationRunRecord,
        evaluation_run_id,
    )

    if evaluation_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation run not found",
        )

    comparison_result = await session.execute(
        select(ComparisonRecord)
        .where(
            ComparisonRecord.evaluation_run_id
            == evaluation_run_id
        )
        .order_by(ComparisonRecord.id.asc())
    )

    comparisons = comparison_result.scalars().all()

    comparison_responses = []
    total_tasks = 0

    for comparison in comparisons:
        task_result = await session.execute(
            select(TaskRecord)
            .where(
                TaskRecord.comparison_id == comparison.id
            )
            .order_by(TaskRecord.created_at.asc())
        )

        tasks = task_result.scalars().all()

        total_tasks += len(tasks)

        comparison_responses.append(
            EvaluationRunComparisonResponse(
                evaluation_case_id=comparison.evaluation_case_id,
                comparison_id=comparison.id,
                prompt=comparison.prompt,
                total=len(tasks),
                tasks=[
                    TaskResponse.model_validate(task)
                    for task in tasks
                ],
            )
        )

    return EvaluationRunResponse(
        evaluation_run_id=evaluation_run.id,
        dataset_id=evaluation_run.dataset_id,
        total_cases=len(comparisons),
        total_comparisons=len(comparisons),
        total_tasks=total_tasks,
        comparisons=comparison_responses,
    )


@app.post(
    "/evaluation-runs/{evaluation_run_id}/run",
    response_model=EvaluationRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_evaluation_run(
    evaluation_run_id: int,
    background_tasks: BackgroundTasks,
    session: SessionDep,
) -> EvaluationRunResponse:
    """提交一次 EvaluationRun 中的全部模型任务。"""

    evaluation_run = await session.get(
        EvaluationRunRecord,
        evaluation_run_id,
    )

    if evaluation_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation run not found",
        )

    # 查询此次 EvaluationRun 下的所有 Comparison
    comparison_result = await session.execute(
        select(ComparisonRecord)
        .where(
            ComparisonRecord.evaluation_run_id
            == evaluation_run_id
        )
        .order_by(ComparisonRecord.id.asc())
    )

    comparisons = comparison_result.scalars().all()

    if not comparisons:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Evaluation run has no comparisons",
        )

    comparison_ids = [
        comparison.id
        for comparison in comparisons
    ]

    # 一次查询出所有 Comparison 下的 Task
    task_result = await session.execute(
        select(TaskRecord)
        .where(
            TaskRecord.comparison_id.in_(
                comparison_ids
            )
        )
        .order_by(TaskRecord.created_at.asc())
    )

    tasks = task_result.scalars().all()

    if not tasks:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Evaluation run has no tasks",
        )

    # 目前 EvaluationRun 只允许执行一次
    if any(
        task.status != TaskStatus.PENDING.value
        for task in tasks
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Evaluation run cannot be run",
        )

    # 整批任务先统一进入 PROCESSING
    for task in tasks:
        task.status = TaskStatus.PROCESSING.value
        task.result = None
        task.error = None

    await session.commit()

    for task in tasks:
        await session.refresh(task)

    task_ids = [
        task.task_id
        for task in tasks
    ]

    background_tasks.add_task(
        execute_evaluation_run_tasks,
        task_ids,
    )

    # 将 Task 按 Comparison 分组，方便构造响应
    tasks_by_comparison: dict[int, list[TaskRecord]] = {}

    for task in tasks:
        if task.comparison_id is None:
            continue

        tasks_by_comparison.setdefault(
            task.comparison_id,
            [],
        ).append(task)

    comparison_responses = []

    for comparison in comparisons:
        comparison_tasks = tasks_by_comparison.get(
            comparison.id,
            [],
        )

        comparison_responses.append(
            EvaluationRunComparisonResponse(
                evaluation_case_id=comparison.evaluation_case_id,
                comparison_id=comparison.id,
                prompt=comparison.prompt,
                total=len(comparison_tasks),
                tasks=[
                    TaskResponse.model_validate(task)
                    for task in comparison_tasks
                ],
            )
        )

    return EvaluationRunResponse(
        evaluation_run_id=evaluation_run.id,
        dataset_id=evaluation_run.dataset_id,
        total_cases=len(comparisons),
        total_comparisons=len(comparisons),
        total_tasks=len(tasks),
        comparisons=comparison_responses,
    )


@app.post(
    "/evaluation-runs/{evaluation_run_id}/evaluate",
    response_model=EvaluationRunEvaluateResponse,
)
async def evaluate_evaluation_run_endpoint(
    evaluation_run_id: int,
    payload: EvaluationRunEvaluateRequest | None = None,
    session: SessionDep = None,
) -> EvaluationRunEvaluateResponse:
    """使用指定 Evaluator 评测一个已完成的 EvaluationRun。"""

    evaluation_run = await session.get(
        EvaluationRunRecord,
        evaluation_run_id,
    )

    if evaluation_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation run not found",
        )

    evaluator_type = (
        payload.evaluator
        if payload is not None
        else EvaluatorType.KEYWORD_MATCH
    )

    evaluator = create_evaluator(evaluator_type)

    try:
        evaluation = await evaluate_evaluation_run(
            session,
            evaluation_run_id=evaluation_run_id,
            evaluator=evaluator,
        )
    except EvaluationRunNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return EvaluationRunEvaluateResponse(
        evaluation_run_id=evaluation_run_id,
        evaluator_name=evaluation.evaluator_name,
        evaluator_version=evaluation.evaluator_version,
        evaluated_tasks=len(evaluation.results),
        skipped_tasks=[
            SkippedEvaluationTaskResponse(
                task_id=item.task_id,
                reason=item.reason,
            )
            for item in evaluation.skipped_tasks
        ],
        results=[
            EvaluationResultResponse.model_validate(item)
            for item in evaluation.results
        ],
    )


@app.get(
    "/evaluation-runs/{evaluation_run_id}/report",
    response_model=EvaluationRunReportResponse,
)
async def get_evaluation_run_report(
    evaluation_run_id: int,
    session: SessionDep,
    evaluator: EvaluatorType = Query(
        default=EvaluatorType.LLM_JUDGE,
    ),
    evaluator_version: str | None = Query(
        default=None,
        min_length=1,
        max_length=50,
    ),
) -> EvaluationRunReportResponse:
    """实时生成一次 EvaluationRun 的聚合报告。"""

    evaluation_run = await session.get(
        EvaluationRunRecord,
        evaluation_run_id,
    )

    if evaluation_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation run not found",
        )

    current_evaluator = create_evaluator(evaluator)

    selected_version = (
        evaluator_version
        or current_evaluator.version
    )

    try:
        report = await build_evaluation_run_report(
            session,
            evaluation_run_id=evaluation_run_id,
            dataset_id=evaluation_run.dataset_id,
            evaluator_name=evaluator.value,
            evaluator_version=selected_version,
        )
    except EvaluationReportNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return EvaluationRunReportResponse.model_validate(
        report
    )


@app.post(
    "/comparisons",
    response_model=ComparisonResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comparison(
    payload: ComparisonCreate,
    session: AsyncSession = Depends(get_session),
) -> ComparisonResponse:
    """为同一个Prompt创建多条模型任务。"""

    comparison = ComparisonRecord(prompt=payload.prompt)    
    session.add(comparison)
    await session.flush()

    tasks = [
        _build_task_record(
            prompt=payload.prompt,
            requested_model=model.value,
            comparison_id=comparison.id,
        )
        for model in payload.models
    ]

    session.add_all(tasks)
    await session.commit()
    await session.refresh(comparison)

    for task in tasks:
        await session.refresh(task)

    return ComparisonResponse(
        comparison_id=comparison.id,
        prompt=payload.prompt,
        total=len(tasks),
        tasks=[
            TaskResponse.model_validate(task)
            for task in tasks
        ],
    )

@app.get(
        "/comparisons/{comparison_id}",
        response_model=ComparisonResponse,
) 
async def get_comparison(
    comparison_id: int,
    session: SessionDep,
) -> ComparisonResponse:
    """查询一次模型对比及其全部子任务。"""

    comparison = await session.get(
        ComparisonRecord,
        comparison_id,
    )

    if comparison is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comparison not found",
        )

    result = await session.execute(
        select(TaskRecord).where(TaskRecord.comparison_id == comparison_id).order_by(TaskRecord.created_at.asc())
    )

    tasks = result.scalars().all()

    return ComparisonResponse(
        comparison_id=comparison.id,
        prompt=comparison.prompt,
        total=len(tasks),
        tasks=[TaskResponse.model_validate(task) for task in tasks],
    )

@app.post(
        "/comparisons/{comparison_id}/run",
        response_model=ComparisonResponse,
        status_code=status.HTTP_202_ACCEPTED,
)
async def run_comparison(
    comparison_id: int,
    background_tasks: BackgroundTasks,
    session: SessionDep,
) -> ComparisonResponse:
    """提交一次模型对比中的全部任务。"""

    comparison = await session.get(
        ComparisonRecord,
        comparison_id,
    )

    if comparison is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comparison not found",
        )

    result = await session.execute(
        select(TaskRecord).where(TaskRecord.comparison_id == comparison_id).order_by(TaskRecord.created_at.asc())
    )

    tasks = result.scalars().all()

    if not tasks:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Comparison has no tasks",
        )

    if any(task.status != TaskStatus.PENDING.value for task in tasks):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Comparison cannot be run",
        )

    for task in tasks:
        task.status = TaskStatus.PROCESSING.value
        task.result = None
        task.error = None

    await session.commit()

    task_ids = [task.task_id for task in tasks]

    background_tasks.add_task(execute_comparison_tasks, task_ids)

    return ComparisonResponse(
        comparison_id=comparison.id,
        prompt=comparison.prompt,
        total=len(tasks),
        tasks = [TaskResponse.model_validate(task) for task in tasks],
    )


@app.get("/tasks", response_model=TaskListResponse)
async def list_tasks(
    session: SessionDep,
    task_status: TaskStatus | None=None,
    limit: int=Query(default=20, ge=1, le=100),
    offset: int=Query(default=0, ge=0),
) -> TaskListResponse:
    """分页查询任务，并支持按状态筛选。"""

    query = select(TaskRecord)
    count_query = select(func.count()).select_from(TaskRecord)

    if task_status is not None:
        query = query.where(TaskRecord.status == task_status.value)
        count_query = count_query.where(TaskRecord.status == task_status.value)

    query = (
        query
        .order_by(TaskRecord.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    result = await session.execute(query)
    records = result.scalars().all()

    total = await session.scalar(count_query)

    return TaskListResponse(
        items=[
            TaskResponse.model_validate(record)
            for record in records
        ],
        total=total or 0,
        limit=limit,
        offset=offset
    )

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


@app.get(
    "/tasks/{task_id}/evaluation-results",
    response_model=list[EvaluationResultResponse],
)
async def list_task_evaluation_results(
    task_id: str,
    session: SessionDep,
) -> list[EvaluationResultResponse]:
    """查询一个 Task 的全部质量评估结果。"""

    task = await session.get(TaskRecord, task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    result = await session.execute(
        select(EvaluationResultRecord)
        .where(
            EvaluationResultRecord.task_id == task_id
        )
        .order_by(
            EvaluationResultRecord.created_at.asc()
        )
    )

    evaluation_results = result.scalars().all()

    return [
        EvaluationResultResponse.model_validate(item)
        for item in evaluation_results
    ]


@app.post(
    "/tasks/{task_id}/run",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    session: SessionDep,
) -> TaskResponse:
    """将处于PENDING状态的任务提交到后台执行。"""

    task = await session.get(TaskRecord, task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    # 只有尚未执行的PENDING任务才能提交。
    if task.status != TaskStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task cannot be run from status {task.status}",
        )

    task.status = TaskStatus.PROCESSING.value
    task.result = None
    task.error = None

    await session.commit()
    await session.refresh(task)

    logger.info(
        "task_submitted task_id=%s status=%s",
        task.task_id,
        task.status,
    )

    background_tasks.add_task(
        execute_task,
        task.task_id,
    )

    return TaskResponse.model_validate(task)