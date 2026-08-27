import {
  ArrowRight,
  Boxes,
  CheckCircle2,
  Clock3,
  Cpu,
  Database,
  FlaskConical,
  Plus,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  MetricCard,
  StatusBadge,
  formatDate,
} from "../components/ui";
import type {
  DatasetListResponse,
  EvaluationRunListResponse,
} from "../types";

export function OverviewPage() {
  const [datasets, setDatasets] =
    useState<DatasetListResponse | null>(null);
  const [runs, setRuns] =
    useState<EvaluationRunListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [datasetData, runData] = await Promise.all([
        api.listDatasets(),
        api.listRuns(),
      ]);
      setDatasets(datasetData);
      setRuns(runData);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "无法连接 EvalFlow API",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const models = useMemo(
    () =>
      new Set(
        runs?.items.flatMap((run) => run.models) ?? [],
      ),
    [runs],
  );

  const completedRuns =
    runs?.items.filter((run) =>
      ["COMPLETED", "PARTIAL_FAILED", "FAILED"].includes(
        run.status,
      ),
    ).length ?? 0;

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div className="page-stack">
      <section className="intro-panel">
        <div>
          <div className="eyebrow">LLM evaluation workspace</div>
          <h1>让模型选择和 Prompt 优化有据可依</h1>
          <p>
            在同一数据集与评估标准下运行多模型对比，从质量、延迟、
            Token 与具体 Bad Case 四个层面解释模型表现。
          </p>
          <div className="intro-actions">
            <Link className="button primary" to="/runs/new">
              <Plus size={17} />
              创建评测
            </Link>
            {runs && runs.items.length > 0 && (
              <Link
                className="button ghost"
                to={`/runs/${runs.items[0].evaluation_run_id}/report`}
              >
                查看最近报告
                <ArrowRight size={16} />
              </Link>
            )}
          </div>
        </div>
        <div className="intro-flow">
          <div className="flow-step active">
            <Database size={19} />
            <div>
              <strong>固定数据集</strong>
              <span>保证比较公平、可重复</span>
            </div>
          </div>
          <div className="flow-line" />
          <div className="flow-step">
            <Cpu size={19} />
            <div>
              <strong>多模型执行</strong>
              <span>受控并发，单任务失败隔离</span>
            </div>
          </div>
          <div className="flow-line" />
          <div className="flow-step">
            <FlaskConical size={19} />
            <div>
              <strong>质量评估</strong>
              <span>规则评估或 LLM-as-a-Judge</span>
            </div>
          </div>
        </div>
      </section>

      <section className="metric-grid four">
        <MetricCard
          label="评测数据集"
          value={datasets?.total ?? 0}
          hint="可复用的标准测试集合"
          icon={<Database size={18} />}
          tone="blue"
        />
        <MetricCard
          label="评测运行"
          value={runs?.total ?? 0}
          hint="已创建的模型对比实验"
          icon={<Boxes size={18} />}
        />
        <MetricCard
          label="已结束运行"
          value={completedRuns}
          hint="包含完成与部分失败"
          icon={<CheckCircle2 size={18} />}
          tone="green"
        />
        <MetricCard
          label="已使用模型"
          value={models.size}
          hint={
            models.size > 0
              ? Array.from(models).join(" · ")
              : "尚无执行记录"
          }
          icon={<Cpu size={18} />}
        />
      </section>

      <section className="content-card">
        <div className="section-header">
          <div>
            <div className="section-kicker">Recent runs</div>
            <h2>最近评测记录</h2>
            <p>从运行状态进入任务监控或模型对比报告。</p>
          </div>
          <Link className="text-link" to="/runs/new">
            新建评测
            <ArrowRight size={15} />
          </Link>
        </div>

        {runs && runs.items.length > 0 ? (
          <div className="run-table" role="table">
            <div className="run-table-row run-table-head" role="row">
              <span>评测 / 数据集</span>
              <span>模型</span>
              <span>评估器</span>
              <span>任务进度</span>
              <span>状态</span>
              <span />
            </div>
            {runs.items.slice(0, 8).map((run) => {
              const terminal =
                run.successful_tasks + run.failed_tasks;
              const progress =
                run.total_tasks === 0
                  ? 0
                  : Math.round(
                      (terminal / run.total_tasks) * 100,
                    );

              return (
                <div
                  className="run-table-row"
                  role="row"
                  key={run.evaluation_run_id}
                >
                  <div>
                    <strong>
                      Run #{run.evaluation_run_id}
                    </strong>
                    <span>{run.dataset_name}</span>
                    <small>
                      <Clock3 size={12} />
                      {formatDate(run.created_at)}
                    </small>
                  </div>
                  <div className="model-tags">
                    {run.models.map((model) => (
                      <span key={model}>{model}</span>
                    ))}
                  </div>
                  <div>
                    <span className="evaluator-label">
                      {run.evaluator_name === "keyword_match"
                        ? "Keyword"
                        : "LLM Judge"}
                    </span>
                    <small>v{run.evaluator_version}</small>
                  </div>
                  <div className="progress-cell">
                    <div>
                      <span>{terminal}/{run.total_tasks}</span>
                      <strong>{progress}%</strong>
                    </div>
                    <div className="progress-track">
                      <span style={{ width: `${progress}%` }} />
                    </div>
                  </div>
                  <StatusBadge status={run.status} />
                  <Link
                    className="row-action"
                    to={
                      ["COMPLETED", "PARTIAL_FAILED", "FAILED"].includes(
                        run.status,
                      )
                        ? `/runs/${run.evaluation_run_id}/report`
                        : `/runs/${run.evaluation_run_id}`
                    }
                    aria-label={`打开 Run ${run.evaluation_run_id}`}
                  >
                    <ArrowRight size={17} />
                  </Link>
                </div>
              );
            })}
          </div>
        ) : (
          <EmptyState
            title="还没有评测记录"
            description="选择一个已有数据集，创建第一次双模型评测。"
            action={
              <Link className="button primary" to="/runs/new">
                <Plus size={16} />
                创建评测
              </Link>
            }
          />
        )}
      </section>
    </div>
  );
}
