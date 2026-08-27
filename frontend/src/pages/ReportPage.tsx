import {
  AlertCircle,
  ArrowLeft,
  ArrowUpRight,
  CheckCircle2,
  ChevronRight,
  CircleDashed,
  Clock3,
  Coins,
  Cpu,
  Gauge,
  KeyRound,
  Layers3,
  RefreshCw,
  Sparkles,
  Target,
  Timer,
  TriangleAlert,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api";
import {
  ErrorState,
  LoadingState,
  MetricCard,
  ResultMark,
  compactNumber,
  formatDate,
  formatLatency,
  formatPercent,
  formatScore,
} from "../components/ui";
import type {
  EvaluationReport,
  EvaluationRun,
  EvaluatorType,
  ModelReport,
  ReportSample,
} from "../types";

type FilterType = "all" | "quality" | "execution" | "unassessed";

export function ReportPage() {
  const { runId } = useParams();
  const numericRunId = Number(runId);
  const [run, setRun] = useState<EvaluationRun | null>(null);
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [evaluator, setEvaluator] = useState<EvaluatorType>("keyword_match");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterType>("all");
  const [selectedSample, setSelectedSample] = useState<ReportSample | null>(null);

  useEffect(() => {
    api
      .getRun(numericRunId)
      .then((runData) => {
        setRun(runData);
        setEvaluator(runData.evaluator_name);
      })
      .catch((loadError: Error) => setError(loadError.message));
  }, [numericRunId]);

  const loadReport = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const reportData = await api.getReport(numericRunId, evaluator);
      setReport(reportData);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "无法生成评测报告");
      setReport(null);
    } finally {
      setLoading(false);
    }
  }, [evaluator, numericRunId]);

  useEffect(() => {
    void loadReport();
  }, [loadReport]);

  const filterCounts = useMemo(() => {
    const samples = report?.samples ?? [];
    return {
      all: samples.length,
      quality: samples.filter((sample) =>
        sample.tasks.some((task) => task.status === "SUCCESS" && task.passed === false),
      ).length,
      execution: samples.filter((sample) =>
        sample.tasks.some((task) => task.status === "FAILED"),
      ).length,
      unassessed: samples.filter((sample) =>
        sample.tasks.some((task) => task.status === "SUCCESS" && task.passed === null),
      ).length,
    };
  }, [report]);

  const filteredSamples = useMemo(() => {
    const samples = report?.samples ?? [];
    if (filter === "quality") {
      return samples.filter((sample) =>
        sample.tasks.some((task) => task.status === "SUCCESS" && task.passed === false),
      );
    }
    if (filter === "execution") {
      return samples.filter((sample) =>
        sample.tasks.some((task) => task.status === "FAILED"),
      );
    }
    if (filter === "unassessed") {
      return samples.filter((sample) =>
        sample.tasks.some((task) => task.status === "SUCCESS" && task.passed === null),
      );
    }
    return samples;
  }, [filter, report]);

  if (loading) return <LoadingState label="正在实时聚合质量与效率报告…" />;
  if (error || !report) {
    return (
      <ErrorState
        message={error ?? "报告暂不可用"}
        onRetry={() => void loadReport()}
      />
    );
  }

  const conclusion = buildConclusion(report.models);

  return (
    <div className="page-stack report-page">
      <section className="report-hero">
        <div>
          <Link className="back-link" to={"/runs/" + numericRunId}>
            <ArrowLeft size={15} />
            返回运行详情
          </Link>
          <div className="run-title-line">
            <span>Run #{report.evaluation_run_id}</span>
            <span className="report-ready"><CheckCircle2 size={14} />报告已生成</span>
          </div>
          <h1>{conclusion}</h1>
          <p>
            报告同时保留质量、覆盖率、执行失败、延迟与 Token，
            可从汇总结果直接回到每个模型回答。
          </p>
          <div className="run-meta">
            {run && <span><Clock3 size={14} />{formatDate(run.created_at)}</span>}
            <span><Layers3 size={14} />{report.overall.total_tasks} 个模型任务</span>
            <span><Target size={14} />评测覆盖率 {formatPercent(report.overall.evaluation_coverage)}</span>
          </div>
        </div>
        <div className="report-controls">
          <div className="evaluator-switch" aria-label="切换评估器">
            <button
              className={evaluator === "keyword_match" ? "active" : ""}
              onClick={() => setEvaluator("keyword_match")}
            >
              <KeyRound size={15} />
              Keyword
            </button>
            <button
              className={evaluator === "llm_judge" ? "active" : ""}
              onClick={() => setEvaluator("llm_judge")}
            >
              <Sparkles size={15} />
              LLM Judge
            </button>
          </div>
          <button className="icon-button" onClick={() => void loadReport()} aria-label="刷新报告">
            <RefreshCw size={17} />
          </button>
        </div>
      </section>

      <div className="report-context-strip">
        <span className="context-label">当前评估标准</span>
        <strong>{report.evaluator_name} / {report.evaluator_version}</strong>
        <span className="context-divider" />
        <span>
          {report.evaluator_name === "keyword_match"
            ? "确定性关键词覆盖：命中全部预期关键词即通过"
            : "语义质量判断：Judge 评分达到 70 分即通过"}
        </span>
        <span className="context-spacer" />
        <span className="traceable"><CheckCircle2 size={14} />配置已随结果保存，可追溯</span>
      </div>

      <section className="metric-grid four">
        <MetricCard
          label="平均质量分"
          value={formatScore(report.overall.average_score)}
          hint="0–100，保留原始评估维度"
          icon={<Target size={18} />}
          tone="blue"
        />
        <MetricCard
          label="质量通过率"
          value={formatPercent(report.overall.pass_rate)}
          hint={report.overall.quality_failed_tasks + " 个质量 Bad Case"}
          icon={<CheckCircle2 size={18} />}
          tone="green"
        />
        <MetricCard
          label="评测覆盖率"
          value={formatPercent(report.overall.evaluation_coverage)}
          hint={report.overall.unevaluated_tasks + " 个成功任务尚未评估"}
          icon={<Gauge size={18} />}
        />
        <MetricCard
          label="执行成功率"
          value={formatPercent(report.overall.execution_success_rate)}
          hint={report.overall.failed_tasks + " 个模型调用失败"}
          icon={<Cpu size={18} />}
        />
      </section>

      <section className="report-grid">
        <div className="content-card comparison-card">
          <div className="section-header compact">
            <div>
              <div className="section-kicker">Model comparison</div>
              <h2>质量与效率对比</h2>
              <p>各指标独立呈现，不以单一综合排名掩盖取舍。</p>
            </div>
          </div>
          <div className="model-score-cards">
            {report.models.map((model, index) => (
              <ModelScoreCard model={model} index={index} key={model.requested_model} />
            ))}
          </div>
          <div className="comparison-bars">
            <ComparisonBar
              label="平均质量分"
              models={report.models}
              getValue={(model) => (model.average_score ?? 0) * 100}
              format={(value) => value.toFixed(1)}
              max={100}
            />
            <ComparisonBar
              label="质量通过率"
              models={report.models}
              getValue={(model) => (model.pass_rate ?? 0) * 100}
              format={(value) => Math.round(value) + "%"}
              max={100}
            />
            <ComparisonBar
              label="平均延迟"
              models={report.models}
              getValue={(model) => model.average_latency_ms ?? 0}
              format={(value) => formatLatency(value)}
            />
            <ComparisonBar
              label="Token 总量"
              models={report.models}
              getValue={(model) => model.total_tokens}
              format={(value) => compactNumber(value)}
            />
          </div>
        </div>

        <div className="content-card token-card">
          <div className="section-header compact">
            <div>
              <div className="section-kicker">Token profile</div>
              <h2>Token 构成</h2>
              <p>成本分析保留 input、output、reasoning 与 cache。</p>
            </div>
          </div>
          <div className="token-total">
            <div><Coins size={20} /><span>本次生成总 Token</span></div>
            <strong>{report.overall.total_tokens.toLocaleString()}</strong>
          </div>
          <div className="token-breakdown">
            <TokenLine label="Input" value={report.overall.total_input_tokens} total={report.overall.total_tokens} tone="blue" />
            <TokenLine label="Output" value={report.overall.total_output_tokens} total={report.overall.total_tokens} tone="teal" />
            <TokenLine label="Reasoning" value={report.overall.total_reasoning_tokens} total={report.overall.total_tokens} tone="purple" />
            <TokenLine label="Cache" value={report.overall.total_cached_tokens} total={report.overall.total_tokens} tone="gray" />
          </div>
          <div className="token-note">
            <Timer size={16} />
            <span>
              平均延迟 {formatLatency(report.overall.average_latency_ms)}，
              单任务平均 {Math.round(report.overall.average_total_tokens ?? 0)} Tokens
            </span>
          </div>
        </div>
      </section>

      <section className="content-card cases-card">
        <div className="section-header">
          <div>
            <div className="section-kicker">Case explorer</div>
            <h2>从汇总指标回到具体样本</h2>
            <p>执行失败与质量失败使用不同字段和颜色，避免误判。</p>
          </div>
          <div className="issue-summary">
            <span className="quality"><AlertCircle size={14} />质量失败 {report.overall.quality_failed_tasks}</span>
            <span className="execution"><TriangleAlert size={14} />执行失败 {report.overall.failed_tasks}</span>
          </div>
        </div>

        <div className="filter-tabs">
          <FilterButton label="全部样本" count={filterCounts.all} active={filter === "all"} onClick={() => setFilter("all")} />
          <FilterButton label="质量失败" count={filterCounts.quality} active={filter === "quality"} onClick={() => setFilter("quality")} />
          <FilterButton label="执行失败" count={filterCounts.execution} active={filter === "execution"} onClick={() => setFilter("execution")} />
          <FilterButton label="未评估" count={filterCounts.unassessed} active={filter === "unassessed"} onClick={() => setFilter("unassessed")} />
        </div>

        {filteredSamples.length > 0 ? (
          <div className="sample-list">
            {filteredSamples.map((sample, index) => (
              <button
                className="sample-row"
                key={sample.comparison_id}
                onClick={() => setSelectedSample(sample)}
              >
                <div className="sample-index">C{String(index + 1).padStart(2, "0")}</div>
                <div className="sample-question">
                  <strong>{sample.prompt}</strong>
                  <span>
                    {sample.expected_keywords.length > 0
                      ? "关键词：" + sample.expected_keywords.join("、")
                      : "使用参考答案进行语义评估"}
                  </span>
                </div>
                <div className="sample-model-results">
                  {sample.tasks.map((task) => (
                    <div key={task.task_id}>
                      <span>{task.requested_model}</span>
                      <strong>{formatScore(task.score)}</strong>
                      <ResultMark status={task.status} passed={task.passed} />
                    </div>
                  ))}
                </div>
                <div className="sample-open"><span>查看详情</span><ChevronRight size={17} /></div>
              </button>
            ))}
          </div>
        ) : (
          <div className="compact-empty">
            <CircleDashed size={24} />
            <strong>当前筛选下没有样本</strong>
            <span>这通常意味着本次运行没有此类问题。</span>
          </div>
        )}
      </section>

      {selectedSample && (
        <CaseDrawer sample={selectedSample} onClose={() => setSelectedSample(null)} />
      )}
    </div>
  );
}

function buildConclusion(models: ModelReport[]) {
  if (models.length < 2) return "评测结果已完成聚合";
  const [first, second] = models;
  if (first.average_score === null || second.average_score === null) {
    return "模型执行已结束，部分回答尚未评估";
  }
  const quality =
    first.average_score === second.average_score
      ? "两模型质量得分持平"
      : (first.average_score > second.average_score ? first.requested_model : second.requested_model) + " 质量得分更高";
  const firstLatency = first.average_latency_ms ?? Number.POSITIVE_INFINITY;
  const secondLatency = second.average_latency_ms ?? Number.POSITIVE_INFINITY;
  const speed =
    firstLatency === secondLatency
      ? "响应速度接近"
      : (firstLatency < secondLatency ? first.requested_model : second.requested_model) + " 响应更快";
  return quality + "，" + speed;
}

function ModelScoreCard({ model, index }: { model: ModelReport; index: number }) {
  return (
    <div className="model-score-card">
      <div className="model-score-head">
        <div className={index === 0 ? "model-letter blue" : "model-letter teal"}>
          {String.fromCharCode(65 + index)}
        </div>
        <div><span>模型 {String.fromCharCode(65 + index)}</span><strong>{model.requested_model}</strong></div>
      </div>
      <div className="big-score">
        <strong>{formatScore(model.average_score)}</strong>
        <span>/ 100</span>
      </div>
      <div className="model-score-meta">
        <div><span>通过率</span><strong>{formatPercent(model.pass_rate)}</strong></div>
        <div><span>覆盖率</span><strong>{formatPercent(model.evaluation_coverage)}</strong></div>
        <div><span>平均延迟</span><strong>{formatLatency(model.average_latency_ms)}</strong></div>
      </div>
    </div>
  );
}

function ComparisonBar({
  label,
  models,
  getValue,
  format,
  max,
}: {
  label: string;
  models: ModelReport[];
  getValue: (model: ModelReport) => number;
  format: (value: number) => string;
  max?: number;
}) {
  const values = models.map(getValue);
  const upper = max ?? Math.max(...values, 1);
  return (
    <div className="comparison-bar-row">
      <span>{label}</span>
      <div className="bar-pair">
        {models.map((model, index) => {
          const value = getValue(model);
          return (
            <div key={model.requested_model}>
              <div className="bar-label"><small>{model.requested_model}</small><strong>{format(value)}</strong></div>
              <div className="bar-track"><span className={index === 0 ? "blue" : "teal"} style={{ width: String((value / upper) * 100) + "%" }} /></div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TokenLine({ label, value, total, tone }: { label: string; value: number; total: number; tone: string }) {
  const percent = total === 0 ? 0 : Math.min((value / total) * 100, 100);
  return (
    <div className="token-line">
      <div><span>{label}</span><strong>{value.toLocaleString()}</strong></div>
      <div className="token-track"><span className={tone} style={{ width: String(percent) + "%" }} /></div>
    </div>
  );
}

function FilterButton({ label, count, active, onClick }: { label: string; count: number; active: boolean; onClick: () => void }) {
  return (
    <button className={active ? "active" : ""} onClick={onClick}>
      {label}<span>{count}</span>
    </button>
  );
}

function CaseDrawer({ sample, onClose }: { sample: ReportSample; onClose: () => void }) {
  return (
    <div className="drawer-backdrop" onMouseDown={onClose}>
      <aside className="case-drawer" onMouseDown={(event) => event.stopPropagation()}>
        <header>
          <div>
            <span>Bad Case / Sample detail</span>
            <h2>样本 #{sample.evaluation_case_id ?? sample.comparison_id}</h2>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="关闭详情"><X size={18} /></button>
        </header>
        <div className="drawer-body">
          <section className="drawer-section">
            <span className="drawer-label">用户输入</span>
            <p className="prompt-copy">{sample.prompt}</p>
          </section>
          {sample.reference_answer && (
            <section className="drawer-section reference">
              <span className="drawer-label">参考答案</span>
              <p>{sample.reference_answer}</p>
            </section>
          )}
          {sample.expected_keywords.length > 0 && (
            <section className="drawer-section">
              <span className="drawer-label">预期关键词</span>
              <div className="keyword-tags">{sample.expected_keywords.map((keyword) => <span key={keyword}>{keyword}</span>)}</div>
            </section>
          )}
          <div className="answer-compare">
            {sample.tasks.map((task, index) => (
              <section className="answer-card" key={task.task_id}>
                <header>
                  <div className={index === 0 ? "model-letter blue" : "model-letter teal"}>{String.fromCharCode(65 + index)}</div>
                  <div><span>模型回答</span><strong>{task.requested_model}</strong></div>
                  <ResultMark status={task.status} passed={task.passed} />
                </header>
                <div className="answer-copy">
                  {task.task_error ? (
                    <div className="execution-error"><TriangleAlert size={17} /><div><strong>模型执行失败</strong><p>{task.task_error}</p></div></div>
                  ) : (
                    <p>{task.model_answer || "无模型回答"}</p>
                  )}
                </div>
                <div className="answer-metrics">
                  <div><span>评分</span><strong>{formatScore(task.score)}</strong></div>
                  <div><span>延迟</span><strong>{formatLatency(task.llm_duration_ms)}</strong></div>
                  <div><span>Token</span><strong>{task.total_tokens?.toLocaleString() ?? "N/A"}</strong></div>
                </div>
                <div className={task.passed === false ? "evaluation-reason failed" : "evaluation-reason"}>
                  <span>评分理由</span>
                  <p>{task.evaluation_reason || (task.task_error ? "执行失败不进入质量评分" : "该回答尚未产生评估结果")}</p>
                </div>
              </section>
            ))}
          </div>
        </div>
        <footer>
          <span><ArrowUpRight size={15} />从聚合指标追溯到 Task 与 EvaluationResult</span>
          <button className="button secondary" onClick={onClose}>关闭</button>
        </footer>
      </aside>
    </div>
  );
}
