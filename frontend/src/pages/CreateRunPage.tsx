import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  Cpu,
  Database,
  Gauge,
  KeyRound,
  LoaderCircle,
  Scale,
  Sparkles,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/ui";
import type {
  DatasetDetail,
  DatasetSummary,
  EvaluatorType,
} from "../types";

const models = [
  {
    value: "qwen3.7-flash",
    label: "Qwen 3.7 Flash",
    note: "通义千问 · 响应速度优先",
  },
  {
    value: "glm-5.2",
    label: "GLM 5.2",
    note: "智谱 GLM · 综合能力对照",
  },
];

const steps = [
  { index: 1, label: "选择数据集" },
  { index: 2, label: "配置模型" },
  { index: 3, label: "评估标准" },
  { index: 4, label: "确认并启动" },
];

export function CreateRunPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [datasetDetail, setDatasetDetail] =
    useState<DatasetDetail | null>(null);
  const [datasetId, setDatasetId] = useState<number | null>(null);
  const [modelA, setModelA] = useState("qwen3.7-flash");
  const [modelB, setModelB] = useState("glm-5.2");
  const [evaluator, setEvaluator] =
    useState<EvaluatorType>("keyword_match");
  const [concurrency, setConcurrency] = useState(2);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listDatasets()
      .then((response) => setDatasets(response.items))
      .catch((loadError: Error) => setError(loadError.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (datasetId === null) {
      setDatasetDetail(null);
      return;
    }

    api
      .getDataset(datasetId)
      .then(setDatasetDetail)
      .catch((loadError: Error) => setError(loadError.message));
  }, [datasetId]);

  const selectedDataset = datasets.find(
    (item) => item.dataset_id === datasetId,
  );

  const readiness = useMemo(() => {
    const cases = datasetDetail?.cases ?? [];
    return {
      keyword: cases.filter(
        (item) => item.expected_keywords.length > 0,
      ).length,
      judge: cases.filter((item) => item.reference_answer).length,
      total: cases.length,
    };
  }, [datasetDetail]);

  const canContinue =
    step === 1
      ? datasetId !== null && (selectedDataset?.total_cases ?? 0) > 0
      : step === 2
        ? modelA !== modelB
        : step === 3
          ? evaluator === "keyword_match"
            ? readiness.keyword > 0
            : readiness.judge > 0
          : true;

  async function submit() {
    if (datasetId === null) return;

    setSubmitting(true);
    setError(null);

    try {
      const run = await api.createRun({
        dataset_id: datasetId,
        models: [modelA, modelB],
        evaluator,
        max_concurrency: concurrency,
      });

      await api.startRun(run.evaluation_run_id);
      navigate("/runs/" + run.evaluation_run_id);
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "创建评测失败",
      );
      setSubmitting(false);
    }
  }

  if (loading) return <LoadingState label="正在读取可用数据集…" />;
  if (error && datasets.length === 0) return <ErrorState message={error} />;

  if (datasets.length === 0) {
    return (
      <EmptyState
        title="暂无可用数据集"
        description="请先通过 API 或 Demo 脚本创建包含评测样本的数据集。"
      />
    );
  }

  return (
    <div className="create-layout">
      <aside className="stepper-card">
        <div className="section-kicker">Evaluation setup</div>
        <h2>配置一次公平、可追溯的模型对比</h2>
        <p>数据集、模型、评估器和并发参数会随 Run 保存。</p>
        <div className="stepper">
          {steps.map((item) => (
            <button
              key={item.index}
              className={
                "stepper-item " +
                (step === item.index ? "active " : "") +
                (step > item.index ? "done" : "")
              }
              onClick={() => {
                if (item.index < step) setStep(item.index);
              }}
            >
              <span>{step > item.index ? <Check size={15} /> : item.index}</span>
              <div>
                <small>步骤 {item.index}</small>
                <strong>{item.label}</strong>
              </div>
            </button>
          ))}
        </div>
        <div className="trace-note">
          <KeyRound size={17} />
          <div>
            <strong>为什么要保存配置？</strong>
            <span>便于区分“模型变了”还是“评分标准变了”。</span>
          </div>
        </div>
      </aside>

      <section className="form-card">
        {step === 1 && (
          <>
            <FormHeading
              number="01"
              title="选择评测数据集"
              description="固定测试样本是多模型公平比较与重复验证的基础。"
            />
            <div className="dataset-options">
              {datasets.map((dataset) => {
                const empty = dataset.total_cases === 0;
                return (
                  <button
                    key={dataset.dataset_id}
                    disabled={empty}
                    className={
                      "dataset-option " +
                      (datasetId === dataset.dataset_id ? "selected" : "")
                    }
                    onClick={() => setDatasetId(dataset.dataset_id)}
                  >
                    <div className="option-check">
                      {datasetId === dataset.dataset_id && <Check size={14} />}
                    </div>
                    <Database size={21} />
                    <div>
                      <strong>{dataset.name}</strong>
                      <p>{dataset.description || "未填写数据集说明"}</p>
                      <span>
                        {dataset.total_cases} 条评测样本
                        {empty && " · 暂不可用"}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          </>
        )}

        {step === 2 && (
          <>
            <FormHeading
              number="02"
              title="配置对比模型"
              description="两个模型将收到完全相同的 Case Prompt，并分别记录执行指标。"
            />
            <div className="model-select-grid">
              <ModelSelect label="模型 A" value={modelA} onChange={setModelA} />
              <div className="versus-mark">VS</div>
              <ModelSelect label="模型 B" value={modelB} onChange={setModelB} />
            </div>
            {modelA === modelB && (
              <div className="inline-alert danger">两个对比模型不能相同。</div>
            )}
            <div className="info-strip">
              <Scale size={18} />
              <span>
                EvalFlow 不生成单一“综合排名”，报告会分别保留质量、延迟和
                Token 指标。
              </span>
            </div>
          </>
        )}

        {step === 3 && (
          <>
            <FormHeading
              number="03"
              title="选择评估标准"
              description="规则评估适合确定性检查，LLM Judge 适合语义质量判断。"
            />
            <div className="evaluator-options">
              <EvaluatorOption
                selected={evaluator === "keyword_match"}
                icon={<KeyRound size={20} />}
                title="KeywordEvaluator"
                tag="确定性规则"
                description="检查回答是否覆盖 Case 中预先保存的关键词，结果快速、稳定且容易解释。"
                readiness={readiness.keyword + "/" + readiness.total + " 条样本已配置关键词"}
                onClick={() => setEvaluator("keyword_match")}
              />
              <EvaluatorOption
                selected={evaluator === "llm_judge"}
                icon={<Sparkles size={20} />}
                title="LLM-as-a-Judge"
                tag="语义评分"
                description="根据问题、参考答案与模型回答，从正确性、完整性和相关性进行语义判断。"
                readiness={readiness.judge + "/" + readiness.total + " 条样本含参考答案"}
                onClick={() => setEvaluator("llm_judge")}
                judge
              />
            </div>
            <div className="criteria-card">
              <div>
                <strong>当前评分标准</strong>
                <span>评估器身份与版本将写入 EvaluationResult</span>
              </div>
              <dl>
                <div>
                  <dt>Evaluator</dt>
                  <dd>{evaluator === "keyword_match" ? "keyword_match / 1.0" : "llm_judge / 1.0"}</dd>
                </div>
                <div>
                  <dt>通过条件</dt>
                  <dd>{evaluator === "keyword_match" ? "命中全部预期关键词" : "Judge 评分 ≥ 70"}</dd>
                </div>
                <div>
                  <dt>失败隔离</dt>
                  <dd>Judge 异常不会写入虚假低分</dd>
                </div>
              </dl>
            </div>
          </>
        )}

        {step === 4 && (
          <>
            <FormHeading
              number="04"
              title="确认配置并启动"
              description="任务会在受控并发下执行，单个模型失败不会终止整次评测。"
            />
            <div className="concurrency-control">
              <div className="concurrency-head">
                <div>
                  <Gauge size={19} />
                  <div>
                    <strong>最大并发任务数</strong>
                    <span>本地演示建议设置为 2–3</span>
                  </div>
                </div>
                <strong>{concurrency}</strong>
              </div>
              <input
                type="range"
                min="1"
                max="5"
                value={concurrency}
                onChange={(event) => setConcurrency(Number(event.target.value))}
                aria-label="最大并发任务数"
              />
              <div className="range-labels">
                <span>更稳健</span>
                <span>更快完成</span>
              </div>
            </div>
            <div className="config-summary">
              <SummaryRow
                icon={<Database size={18} />}
                label="数据集"
                value={(selectedDataset?.name ?? "") + " · " + (selectedDataset?.total_cases ?? 0) + " Cases"}
              />
              <SummaryRow
                icon={<Cpu size={18} />}
                label="模型对比"
                value={modelA + "  vs  " + modelB}
              />
              <SummaryRow
                icon={<Scale size={18} />}
                label="评估标准"
                value={evaluator === "keyword_match" ? "KeywordEvaluator / 1.0" : "LLM-as-a-Judge / 1.0"}
              />
              <SummaryRow
                icon={<Gauge size={18} />}
                label="执行策略"
                value={"最大并发 " + concurrency + " · 单任务失败隔离"}
              />
            </div>
            {error && <div className="inline-alert danger">{error}</div>}
          </>
        )}

        <footer className="form-footer">
          <button
            className="button secondary"
            disabled={step === 1 || submitting}
            onClick={() => setStep((current) => current - 1)}
          >
            <ArrowLeft size={16} />
            上一步
          </button>
          {step < 4 ? (
            <button
              className="button primary"
              disabled={!canContinue}
              onClick={() => setStep((current) => current + 1)}
            >
              下一步
              <ArrowRight size={16} />
            </button>
          ) : (
            <button
              className="button primary"
              disabled={submitting}
              onClick={() => void submit()}
            >
              {submitting ? <LoaderCircle className="spin" size={17} /> : <Sparkles size={17} />}
              {submitting ? "正在创建…" : "创建并启动评测"}
            </button>
          )}
        </footer>
      </section>
    </div>
  );
}

function FormHeading({ number, title, description }: { number: string; title: string; description: string }) {
  return (
    <div className="form-heading">
      <span>{number}</span>
      <div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
    </div>
  );
}

function ModelSelect({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  const selected = models.find((model) => model.value === value)!;
  return (
    <label className="model-select-card">
      <span>{label}</span>
      <div className="model-select-icon"><Cpu size={22} /></div>
      <strong>{selected.label}</strong>
      <small>{selected.note}</small>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {models.map((model) => (
          <option value={model.value} key={model.value}>{model.value}</option>
        ))}
      </select>
    </label>
  );
}

function EvaluatorOption({
  selected,
  icon,
  title,
  tag,
  description,
  readiness,
  onClick,
  judge = false,
}: {
  selected: boolean;
  icon: ReactNode;
  title: string;
  tag: string;
  description: string;
  readiness: string;
  onClick: () => void;
  judge?: boolean;
}) {
  return (
    <button className={"evaluator-option " + (selected ? "selected" : "")} onClick={onClick}>
      <div className={"evaluator-icon " + (judge ? "judge" : "")}>{icon}</div>
      <div>
        <div className="option-title-line"><strong>{title}</strong><span>{tag}</span></div>
        <p>{description}</p>
        <div className="readiness-line"><CheckCircle2 size={15} />{readiness}</div>
      </div>
    </button>
  );
}

function SummaryRow({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="summary-row">
      <div>{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
      <CheckCircle2 size={17} />
    </div>
  );
}
