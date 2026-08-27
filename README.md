# EvalFlow

[![Tests](https://github.com/kai666-song/EvalFlow/actions/workflows/tests.yml/badge.svg)](https://github.com/kai666-song/EvalFlow/actions/workflows/tests.yml)

面向 LLM 应用开发过程的大模型质量评估与优化工具。

EvalFlow 通过标准化测试数据集、可重复的 Evaluation Run、多模型横向比较和可扩展 Evaluator Framework，帮助 AI 应用团队：

- 比较不同模型的回答质量和推理成本；
- 在固定数据集上复测 Prompt 或模型调整后的效果；
- 区分模型调用失败和回答质量不合格；
- 发现并结构化分析 Bad Case；
- 为模型选择和 LLM 应用优化提供依据。

EvalFlow 的目标不是构建完整 LLMOps、多租户 SaaS 或 Agent 管理平台，而是聚焦：

```text
AI 应用评测
  + 模型比较
  + 质量分析
  + 优化反馈
```

## 核心工作流

```text
EvaluationDataset
  └── EvaluationCase
        ↓
EvaluationRun
  └── 每条 Case 创建一个 Comparison
        └── 每个模型创建一个 Task
              ↓
        模型生成回答
              ↓
        Evaluator Framework
          ├── KeywordEvaluator
          └── LLMJudgeEvaluator
              ↓
        EvaluationResult
              ↓
        Evaluation Report
          ├── 模型质量指标
          ├── 延迟与 Token 指标
          ├── Execution Bad Case
          └── Quality Bad Case
```

## 已实现能力

### 数据集与可重复实验

- 创建 EvaluationDataset；
- 为 Dataset 添加 EvaluationCase；
- 保存参考答案和确定性关键词规则；
- 基于固定 Dataset 创建可重复 EvaluationRun；
- Run 创建后固化 Case、Comparison 与 Task 的对应关系。

### 多模型执行

当前支持：

- `qwen3.7-flash`
- `glm-5.2`

每个模型执行 Task 会持久化：

- 执行状态；
- 实际模型名；
- LLM 延迟；
- input/output/reasoning/cached/total tokens；
- 模型回答；
- 系统执行错误。

### Evaluator Framework

统一输入：

```text
EvaluationContext
  ├── question
  ├── reference_answer
  ├── model_answer
  └── metadata
```

统一输出：

```text
EvaluationOutcome
  ├── score
  ├── passed
  └── reason
```

当前 Evaluator：

- `keyword_match / 1.0`
  - 使用 Case 中持久化的 `expected_keywords`；
  - 输出关键词覆盖率和缺失项；
  - 规则确定、执行快速、无需额外模型调用。

- `llm_judge / 1.0`
  - 依据问题、参考答案和模型回答进行语义评分；
  - 使用严格 JSON 输出协议；
  - 由服务端计算通过状态；
  - 保存 Judge 模型、Prompt 版本和阈值配置。

### Evaluation Report

Report 按 `requested_model` 动态聚合：

- 执行成功率；
- 评测覆盖率；
- 平均质量分；
- 质量通过率；
- 平均模型延迟；
- 总 Token 与平均 Token。

Report 不单独持久化，而是根据 Task 和 EvaluationResult 实时生成，避免派生数据过期。

### Web 演示工作台

项目包含独立的 React + Vite + TypeScript 前端，直接读取 FastAPI 与
SQLite 中的真实评测数据，覆盖以下产品流程：

- 评测概览：数据集、运行次数、模型和最近评测状态；
- 创建评测：选择数据集、双模型、评估器与受控并发参数；
- 运行详情：自动轮询任务进度，区分成功、等待、执行失败和部分失败；
- 对比报告：质量分、通过率、覆盖率、延迟和 Token 构成；
- Bad Case：筛选质量失败、执行失败和未评估样本，并查看双模型回答与评分理由。

前端不维护独立的演示假数据。界面中的统计与样本内容均来自当前
EvalFlow API；本地已有的真实 Demo Run 可直接用于页面展示。

## 项目验证

- 自动化测试覆盖任务执行、数据集、模型对比、Evaluator、Report、异常恢复与输入校验；
- GitHub Actions 会在 push 和 pull request 时自动运行完整测试；
- 2026-08-25 已使用 Qwen 与 GLM 完成真实端到端 Demo；
- 脱敏后的运行指标见 [`docs/demo_evaluation_summary.json`](docs/demo_evaluation_summary.json)。

真实 Demo 中，4 个生成任务均执行成功，两种 Evaluator 的评测覆盖率均为 100%。关键词规则的总体平均分为 0.854，通过率为 50%；LLM-as-a-Judge 的总体平均分为 0.965，通过率为 100%。两种评测结果的差异也展示了确定性规则可解释、但容易受字面匹配影响的特点。

### Bad Case 分析

EvalFlow 明确区分：

```text
EXECUTION_FAILED
```

模型调用超时、API 错误或服务不可用，使用 `Task.error` 描述。

```text
QUALITY_FAILED
```

模型调用成功，但 Evaluator 判断回答质量不合格，使用 EvaluationResult 的 `score` 和 `reason` 描述。

成功执行但没有指定 Evaluator 结果的 Task 会归入 `unassessed_cases`，不会被误判为低质量。

## 技术栈

- Python 3.12+
- FastAPI
- Pydantic v2
- SQLAlchemy 2.0 Async
- SQLite + aiosqlite
- Alembic
- OpenAI-compatible SDK
- pytest + pytest-asyncio
- uv
- React 19 + TypeScript
- Vite

## 项目结构

```text
app/
  main.py                 FastAPI 路由与任务编排
  models.py               API 请求和响应模型
  db_models.py            SQLAlchemy ORM 模型
  database.py             异步数据库会话
  processor.py            多模型调用适配
  evaluation_service.py   Evaluator 调度与结果持久化
  report_service.py       Report 聚合与 Bad Case 分类
  evaluators/
    base.py               EvaluationContext 和 BaseEvaluator
    keyword.py            KeywordEvaluator
    llm_judge.py          LLMJudgeEvaluator
    factory.py            Evaluator Factory

frontend/
  src/
    pages/                概览、创建、运行详情与报告页面
    components/           工作台布局与通用状态组件
    api.ts                FastAPI 客户端
    types.ts              前后端数据契约
  package.json            前端依赖与构建命令

migrations/               Alembic 数据库迁移
tests/                    自动化测试
scripts/                  Smoke Test 与完整 Demo
output/playwright/         浏览器验收与作品集候选截图
```

## 快速开始

### 1. 安装 uv

请先安装 [uv](https://docs.astral.sh/uv/)。

### 2. 安装依赖

```powershell
uv sync
```

### 3. 创建本地环境变量

```powershell
Copy-Item -LiteralPath ".env.example" -Destination ".env"
```

编辑 `.env`：

```dotenv
DASHSCOPE_API_KEY=your_real_api_key
LLM_BASE_URL=https://your-openai-compatible-endpoint/v1
LLM_MODEL=qwen3.7-flash
LLM_TIMEOUT_SECONDS=30
```

`.env` 已被 `.gitignore` 忽略，不要提交真实密钥。

### 4. 执行数据库迁移

```powershell
uv run alembic upgrade head
```

检查迁移版本：

```powershell
uv run alembic current
```

### 5. 启动后端服务

```powershell
uv run fastapi dev app/main.py
```

服务默认运行在：

```text
http://127.0.0.1:8000
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

### 6. 启动 Web 前端

在新的 PowerShell 窗口中：

~~~powershell
Set-Location -LiteralPath "frontend"
npm install
Copy-Item -LiteralPath ".env.example" -Destination ".env.local"
npm run dev
~~~

前端默认运行在：

~~~text
http://127.0.0.1:5173
~~~

默认 API 地址为 http://127.0.0.1:8000。如需连接其他后端，
编辑 frontend/.env.local：

~~~dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
~~~

生产构建验证：

~~~powershell
npm run build
~~~

### 7. 运行后端测试

```powershell
uv run pytest -q
```

## 完整闭环 Demo

先在一个 PowerShell 窗口启动服务：

```powershell
uv run fastapi dev app/main.py
```

在另一个窗口运行：

```powershell
uv run python scripts/demo_evaluation_pipeline.py
```

Demo 会执行：

```text
创建 Dataset
  → 创建 2 条 Case
  → 创建 2 模型 EvaluationRun
  → 执行 4 个生成 Task
  → KeywordEvaluator
  → LLMJudgeEvaluator
  → 生成两份模型报告
  → 输出 Bad Case
```

完整 Demo 会产生真实模型请求和相应 API 费用。

如果只验证确定性评测和报告，不运行 LLM Judge：

```powershell
uv run python scripts/demo_evaluation_pipeline.py --skip-llm-judge
```

Demo 结果默认保存到：

```text
demo_evaluation_report.json
```

该文件为本地运行产物，不应提交到 Git。

## 已验证的真实 Demo

2026-08-25 使用 2 条 EvaluationCase 和 2 个模型完成端到端验证：

```text
2 Cases
2 Models
4 Generation Tasks
4 Keyword Evaluation Results
4 LLM Judge Evaluation Results
2 Evaluation Reports
```

脱敏后的真实运行摘要：

| 指标 | 结果 |
|---|---:|
| 模型任务执行成功率 | 100% |
| KeywordEvaluator 覆盖率 | 100% |
| KeywordEvaluator 平均分 | 0.854 |
| LLMJudgeEvaluator 覆盖率 | 100% |
| LLMJudgeEvaluator 平均分 | 0.965 |
| 总 Token | 5,607 |

完整的脱敏结构化摘要见 [`docs/demo_evaluation_summary.json`](docs/demo_evaluation_summary.json)。

## 主要 API

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/health` | 健康检查 |
| `POST` | `/tasks` | 创建单模型 Task |
| `POST` | `/tasks/{task_id}/run` | 执行 Task |
| `GET` | `/tasks/{task_id}` | 查询 Task |
| `POST` | `/comparisons` | 创建多模型 Comparison |
| `POST` | `/comparisons/{id}/run` | 执行 Comparison |
| `POST` | `/datasets` | 创建 Dataset |
| `GET` | `/datasets` | 查询 Dataset 列表与 Case 数量 |
| `POST` | `/datasets/{id}/cases` | 添加 EvaluationCase |
| `POST` | `/evaluation-runs` | 创建 EvaluationRun |
| `GET` | `/evaluation-runs` | 查询最近 Run、状态与模型进度 |
| `POST` | `/evaluation-runs/{id}/run` | 执行整个 Run |
| `POST` | `/evaluation-runs/{id}/evaluate` | 执行指定 Evaluator |
| `GET` | `/tasks/{id}/evaluation-results` | 查询 Task 评测结果 |
| `GET` | `/evaluation-runs/{id}/report` | 获取聚合报告和 Bad Case |

执行 KeywordEvaluator：

```json
{
  "evaluator": "keyword_match"
}
```

执行 LLMJudgeEvaluator：

```json
{
  "evaluator": "llm_judge"
}
```

查询指定 Judge 版本报告：

```text
GET /evaluation-runs/1/report?evaluator=llm_judge&evaluator_version=1.0
```

## 核心设计决策

### Task 与 EvaluationResult 解耦

Task 描述模型执行发生了什么；EvaluationResult 描述回答质量怎么样。

因此：

```text
执行失败 ≠ 回答质量差
```

### Evaluator 具有身份和版本

EvaluationResult 保存：

```text
evaluator_name
evaluator_version
evaluator_config
```

这使系统可以区分模型变化和评估标准变化，并保留不同评估版本的历史结果。

### Report 不持久化

Report 是 Task 和 EvaluationResult 的派生数据。当前数据集规模下按请求计算更简单、可靠，也避免同步和缓存失效问题。

### Judge 失败不产生低分结果

Judge 超时、返回非法 JSON 或评分不合法时：

- Task 仍保持 `SUCCESS`；
- 不写入虚假低分；
- 该 Task 进入未评测集合；
- 后续可以重新执行 Judge。

## 当前范围

EvalFlow 当前聚焦单机环境下的 LLM 应用质量评估，不包含：

- 用户和权限系统；
- 多租户；
- 分布式任务队列；
- Kubernetes；
- 企业级复杂 Dashboard 与 BI 系统；
- Agent 生命周期管理。

这种范围控制使项目能够集中展示 AI 评测问题理解、解决方案设计和工程实现能力。
