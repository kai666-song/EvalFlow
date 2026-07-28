# EvalFlow

AI任务与模型评测平台。

## 当前功能

- FastAPI服务与健康检查接口
- Pydantic请求数据校验
- AI任务创建与状态查询
- 后台异步任务执行
- PENDING、PROCESSING、SUCCESS、FAILED状态流转
- 成功与失败异常处理
- 任务生命周期与耗时日志

## 运行项目

```powershell
uv sync
uv run fastapi dev app/main.py
