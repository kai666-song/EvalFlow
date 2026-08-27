import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  Clock3,
  Cpu,
  Gauge,
  LoaderCircle,
  Play,
  RefreshCw,
  Sparkles,
  Timer,
  TriangleAlert,
  Zap,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api } from "../api";
import {
  ErrorState,
  LoadingState,
  MetricCard,
  StatusBadge,
  compactNumber,
  formatDate,
  formatLatency,
} from "../components/ui";
import type {
  DatasetDetail,
  EvaluationRun,
  EvaluationRunStatus,
  Task,
} from "../types";

function getRunStatus(tasks: Task[]): EvaluationRunStatus {
  if (tasks.length === 0 || tasks.every((task) => task.status === "PENDING")) {
    return "PENDING";
  }
  if (tasks.some((task) => ["PENDING", "PROCESSING"].includes(task.status))) {
    return "PROCESSING";
  }
  if (tasks.every((task) => task.status === "SUCCESS")) return "COMPLETED";
  if (tasks.every((task) => task.status === "FAILED")) return "FAILED";
  return "PARTIAL_FAILED";
}

export function RunDetailPage() {
  const { runId } = useParams();
  const navigate = useNavigate();
  const numericRunId = Number(runId);
  const [run, setRun] = useState<EvaluationRun | null>(null);
  const [dataset, setDataset] = useState<DatasetDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      const runData = await api.getRun(numericRunId);
      setRun(runData);
      if (!dataset) {
        const datasetData = await api.getDataset(runData.dataset_id);
        setDataset(datasetData);
      }
      setError(null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "无法读取评测运行");
    } finally {
      if (!quiet) setLoading(false);
    }
  }, [dataset, numericRunId]);

  useEffect(() => {
    void load();
  }, [numericRunId]);

  const tasks = useMemo(
    () => run?.comparisons.flatMap((comparison) => comparison.tasks) ?? [],
    [run],
  );
  const status = getRunStatus(tasks);
  const counts = {
    success: tasks.filter((task) => task.status === "SUCCESS").length,
    failed: tasks.filter((task) => task.status === "FAILED").length,
    processing: tasks.filter((task) => task.status === "PROCESSING").length,
    pending: tasks.filter((task) => task.status === "PENDING").length,
  };
  const terminalCount = counts.success + counts.failed;
  const progress = tasks.length === 0 ? 0 : Math.round((terminalCount / tasks.length) * 100);

  useEffect(() => {
    if (status !== "PROCESSING") return;
    const timer = window.setInterval(() => void load(true), 2500);
    return () => window.clearInterval(timer);
  }, [load, status]);

  const modelGroups = useMemo(() => {
    const groups = new Map<string, Task[]>();
    tasks.forEach((task) => {
      const model = task.requested_model ?? "unknown";
      groups.set(model, [...(groups.get(model) ?? []), task]);
    });
    return Array.from(groups.entries());
  }, [tasks]);

  async function startRun() {
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.startRun(numericRunId);
      setRun(response);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "启动失败");
    } finally {
      setActionLoading(false);
    }
  }

  async function evaluateAndOpenReport() {
    if (!run) return;
    setActionLoading(true);
    setError(null);
    try {
      await api.evaluateRun(numericRunId, run.evaluator_name);
      navigate("/runs/" + numericRunId + "/report");
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "评测失败");
      setActionLoading(false);
    }
  }

  if (loading) return <LoadingState label="正在读取评测运行…" />;
  if (error && !run) return <ErrorState message={error} onRetry={() => void load()} />;
  if (!run) return null;

  const terminal = ["COMPLETED", "PARTIAL_FAILED", "FAILED"].includes(status);

  return (
    <div className="page-stack">
      <section className="run-hero">
        <div className="run-hero-main">
          <div className="run-title-line">
            <StatusBadge status={status} />
            <span>Run #{run.evaluation_run_id}</span>
          </div>
          <h1>{dataset?.name ?? "评测运行"}</h1>
          <p>
            {run.total_cases} 个 Case · {modelGroups.length} 个模型 ·
            最大并发 {run.max_concurrency}
          </p>
          <div className="run-meta">
            <span><Clock3 size={14} />{formatDate(run.created_at)}</span>
            <span><Sparkles size={14} />{run.evaluator_name} / {run.evaluator_version}</span>
            <span><Gauge size={14} />受控并发与单任务失败隔离</span>
          </div>
        </div>
        <div className="run-actions">
          {status === "PENDING" && (
            <button className="button primary" onClick={() => void startRun()} disabled={actionLoading}>
              {actionLoading ? <LoaderCircle className="spin" size={17} /> : <Play size={17} />}
              启动执行
            </button>
          )}
          {terminal && (
            <>
              <button
                className="button primary"
                onClick={() => void evaluateAndOpenReport()}
                disabled={actionLoading || counts.success === 0}
              >
                {actionLoading ? <LoaderCircle className="spin" size={17} /> : <Sparkles size={17} />}
                执行评测并查看报告
              </button>
              <Link className="button secondary" to={"/runs/" + numericRunId + "/report"}>
                <BarChart3 size={17} />
                直接查看报告
              </Link>
            </>
          )}
          <button className="icon-button" onClick={() => void load()} aria-label="刷新">
            <RefreshCw size={17} />
          </button>
        </div>
      </section>

      {error && <div className="inline-alert danger"><AlertTriangle size={17} />{error}</div>}

      <section className="progress-panel">
        <div className="progress-overview">
          <div>
            <span>总体进度</span>
            <strong>{progress}%</strong>
          </div>
          <div className="large-progress-track">
            <span className="success" style={{ width: String((counts.success / tasks.length) * 100) + "%" }} />
            <span className="failed" style={{ width: String((counts.failed / tasks.length) * 100) + "%" }} />
          </div>
          <p>
            {status === "PROCESSING"
              ? "模型任务正在后台执行，页面会自动刷新。"
              : terminal
                ? "所有模型任务均已结束，可执行质量评估或查看已有报告。"
                : "任务已创建，等待提交执行。"}
          </p>
        </div>
        <div className="progress-counts">
          <div><strong>{tasks.length}</strong><span>总任务</span></div>
          <div className="success"><strong>{counts.success}</strong><span>成功</span></div>
          <div className="danger"><strong>{counts.failed}</strong><span>失败</span></div>
          <div><strong>{counts.processing + counts.pending}</strong><span>待完成</span></div>
        </div>
      </section>

      <section className="metric-grid four">
        <MetricCard
          label="执行成功"
          value={counts.success}
          hint="模型调用完成并持久化回答"
          icon={<CheckCircle2 size={18} />}
          tone="green"
        />
        <MetricCard
          label="执行失败"
          value={counts.failed}
          hint="与回答质量失败分开统计"
          icon={<TriangleAlert size={18} />}
        />
        <MetricCard
          label="处理中"
          value={counts.processing}
          hint="当前正在占用并发槽"
          icon={<Zap size={18} />}
          tone="blue"
        />
        <MetricCard
          label="等待执行"
          value={counts.pending}
          hint="将在已有任务结束后启动"
          icon={<Timer size={18} />}
        />
      </section>

      <section className="model-runtime-grid">
        {modelGroups.map(([model, modelTasks], index) => {
          const successful = modelTasks.filter((task) => task.status === "SUCCESS");
          const latencyValues = successful
            .map((task) => task.llm_duration_ms)
            .filter((value): value is number => value !== null);
          const averageLatency =
            latencyValues.length > 0
              ? latencyValues.reduce((sum, value) => sum + value, 0) / latencyValues.length
              : null;
          const tokens = successful.reduce((sum, task) => sum + (task.total_tokens ?? 0), 0);
          return (
            <div className="model-runtime-card" key={model}>
              <div className="model-runtime-title">
                <div className={index === 0 ? "model-letter blue" : "model-letter teal"}>
                  {String.fromCharCode(65 + index)}
                </div>
                <div><span>对比模型 {String.fromCharCode(65 + index)}</span><strong>{model}</strong></div>
                <Cpu size={20} />
              </div>
              <div className="model-runtime-stats">
                <div><span>完成任务</span><strong>{successful.length}/{modelTasks.length}</strong></div>
                <div><span>平均延迟</span><strong>{formatLatency(averageLatency)}</strong></div>
                <div><span>Token 总量</span><strong>{compactNumber(tokens)}</strong></div>
              </div>
              <div className="task-dot-row">
                {modelTasks.map((task) => (
                  <span key={task.task_id} className={task.status.toLowerCase()} title={task.status} />
                ))}
              </div>
            </div>
          );
        })}
      </section>

      <section className="content-card">
        <div className="section-header">
          <div>
            <div className="section-kicker">Task execution</div>
            <h2>样本与单任务执行状态</h2>
            <p>任何一个 Task 失败都不会阻断其他模型与样本。</p>
          </div>
        </div>
        <div className="task-table">
          <div className="task-table-head">
            <span>样本</span><span>模型</span><span>状态</span><span>延迟</span><span>Token</span><span>结果 / 错误</span>
          </div>
          {run.comparisons.flatMap((comparison, caseIndex) =>
            comparison.tasks.map((task, taskIndex) => (
              <div className="task-table-row" key={task.task_id}>
                <div>
                  {taskIndex === 0 ? (
                    <>
                      <strong>Case {String(caseIndex + 1).padStart(2, "0")}</strong>
                      <span>{comparison.prompt}</span>
                    </>
                  ) : <span className="same-case">同一测试样本</span>}
                </div>
                <strong>{task.requested_model}</strong>
                <StatusBadge status={task.status} />
                <span>{formatLatency(task.llm_duration_ms)}</span>
                <span>{task.total_tokens === null ? "—" : task.total_tokens.toLocaleString()}</span>
                <span className={task.error ? "task-message error" : "task-message"}>
                  {task.error || task.result || (task.status === "PROCESSING" ? "正在调用模型…" : "等待执行")}
                </span>
              </div>
            )),
          )}
        </div>
      </section>
    </div>
  );
}
