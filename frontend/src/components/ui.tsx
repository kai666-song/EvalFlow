import {
  AlertCircle,
  CheckCircle2,
  CircleDashed,
  LoaderCircle,
  RefreshCw,
  TriangleAlert,
} from "lucide-react";
import type { ReactNode } from "react";

import type {
  EvaluationRunStatus,
  TaskStatus,
} from "../types";

type DisplayStatus = EvaluationRunStatus | TaskStatus;

const statusMap: Record<
  DisplayStatus,
  { label: string; tone: string }
> = {
  PENDING: { label: "待执行", tone: "neutral" },
  PROCESSING: { label: "运行中", tone: "info" },
  SUCCESS: { label: "执行成功", tone: "success" },
  COMPLETED: { label: "已完成", tone: "success" },
  PARTIAL_FAILED: { label: "部分失败", tone: "warning" },
  FAILED: { label: "执行失败", tone: "danger" },
};

export function StatusBadge({ status }: { status: DisplayStatus }) {
  const item = statusMap[status];
  return (
    <span className={`status-badge ${item.tone}`}>
      <span />
      {item.label}
    </span>
  );
}

export function MetricCard({
  label,
  value,
  hint,
  icon,
  tone = "default",
}: {
  label: string;
  value: ReactNode;
  hint: string;
  icon: ReactNode;
  tone?: "default" | "blue" | "green";
}) {
  return (
    <div className={`metric-card ${tone}`}>
      <div className="metric-card-head">
        <span>{label}</span>
        <div className="metric-icon">{icon}</div>
      </div>
      <div className="metric-value">{value}</div>
      <div className="metric-hint">{hint}</div>
    </div>
  );
}

export function LoadingState({
  label = "正在读取真实评测数据…",
}: {
  label?: string;
}) {
  return (
    <div className="page-state">
      <LoaderCircle className="spin" size={26} />
      <strong>{label}</strong>
      <span>请稍候，数据来自 EvalFlow API</span>
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="page-state error-state">
      <AlertCircle size={28} />
      <strong>数据加载失败</strong>
      <span>{message}</span>
      {onRetry && (
        <button className="button secondary" onClick={onRetry}>
          <RefreshCw size={16} />
          重新加载
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-state empty-state">
      <CircleDashed size={30} />
      <strong>{title}</strong>
      <span>{description}</span>
      {action}
    </div>
  );
}

export function ResultMark({
  status,
  passed,
}: {
  status: TaskStatus;
  passed: boolean | null;
}) {
  if (status === "FAILED") {
    return (
      <span className="result-mark danger">
        <TriangleAlert size={15} />
        执行失败
      </span>
    );
  }

  if (passed === null) {
    return (
      <span className="result-mark neutral">
        <CircleDashed size={15} />
        未评估
      </span>
    );
  }

  return passed ? (
    <span className="result-mark success">
      <CheckCircle2 size={15} />
      质量通过
    </span>
  ) : (
    <span className="result-mark warning">
      <AlertCircle size={15} />
      质量未通过
    </span>
  );
}

export function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

export function formatPercent(value: number | null) {
  return value === null ? "N/A" : `${Math.round(value * 100)}%`;
}

export function formatScore(value: number | null) {
  return value === null ? "N/A" : (value * 100).toFixed(1);
}

export function formatLatency(value: number | null) {
  if (value === null) return "N/A";
  return value >= 1000
    ? `${(value / 1000).toFixed(2)} s`
    : `${Math.round(value)} ms`;
}

export function compactNumber(value: number) {
  return new Intl.NumberFormat("zh-CN", {
    notation: value >= 10000 ? "compact" : "standard",
    maximumFractionDigits: 1,
  }).format(value);
}
