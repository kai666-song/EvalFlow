export type TaskStatus = "PENDING" | "PROCESSING" | "SUCCESS" | "FAILED";

export type EvaluationRunStatus =
  | "PENDING"
  | "PROCESSING"
  | "COMPLETED"
  | "PARTIAL_FAILED"
  | "FAILED";

export type EvaluatorType = "keyword_match" | "llm_judge";

export interface DatasetSummary {
  dataset_id: number;
  name: string;
  description: string | null;
  created_at: string;
  total_cases: number;
}

export interface DatasetListResponse {
  items: DatasetSummary[];
  total: number;
}

export interface EvaluationCase {
  case_id: number;
  dataset_id: number;
  prompt: string;
  reference_answer: string | null;
  expected_keywords: string[];
  created_at: string;
}

export interface DatasetDetail extends DatasetSummary {
  cases: EvaluationCase[];
}

export interface Task {
  task_id: string;
  prompt: string;
  status: TaskStatus;
  requested_model: string | null;
  model_name: string | null;
  llm_duration_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  reasoning_tokens: number | null;
  cached_tokens: number | null;
  total_tokens: number | null;
  result: string | null;
  error: string | null;
  created_at: string;
}

export interface RunComparison {
  evaluation_case_id: number;
  comparison_id: number;
  prompt: string;
  total: number;
  tasks: Task[];
}

export interface EvaluationRun {
  evaluation_run_id: number;
  dataset_id: number;
  evaluator_name: EvaluatorType;
  evaluator_version: string;
  max_concurrency: number;
  created_at: string;
  total_cases: number;
  total_comparisons: number;
  total_tasks: number;
  comparisons: RunComparison[];
}

export interface EvaluationRunSummary {
  evaluation_run_id: number;
  dataset_id: number;
  dataset_name: string;
  evaluator_name: EvaluatorType;
  evaluator_version: string;
  max_concurrency: number;
  created_at: string;
  models: string[];
  status: EvaluationRunStatus;
  total_tasks: number;
  pending_tasks: number;
  processing_tasks: number;
  successful_tasks: number;
  failed_tasks: number;
}

export interface EvaluationRunListResponse {
  items: EvaluationRunSummary[];
  total: number;
}

export interface ReportMetrics {
  total_tasks: number;
  successful_tasks: number;
  failed_tasks: number;
  evaluated_tasks: number;
  passed_tasks: number;
  quality_failed_tasks: number;
  unevaluated_tasks: number;
  execution_success_rate: number;
  evaluation_coverage: number;
  average_score: number | null;
  pass_rate: number | null;
  average_latency_ms: number | null;
  total_tokens: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_reasoning_tokens: number;
  total_cached_tokens: number;
  average_total_tokens: number | null;
}

export interface ModelReport extends ReportMetrics {
  requested_model: string;
}

export interface ReportTask {
  task_id: string;
  requested_model: string;
  status: TaskStatus;
  model_answer: string | null;
  task_error: string | null;
  llm_duration_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  reasoning_tokens: number | null;
  cached_tokens: number | null;
  total_tokens: number | null;
  score: number | null;
  passed: boolean | null;
  evaluation_reason: string | null;
}

export interface ReportSample {
  evaluation_case_id: number | null;
  comparison_id: number;
  prompt: string;
  reference_answer: string | null;
  expected_keywords: string[];
  tasks: ReportTask[];
}

export interface BadCase {
  issue_type: "EXECUTION_FAILED" | "QUALITY_FAILED";
  evaluation_case_id: number | null;
  comparison_id: number;
  task_id: string;
  requested_model: string;
  prompt: string;
  reference_answer: string | null;
  model_answer: string | null;
  score: number | null;
  task_error: string | null;
  evaluation_reason: string | null;
}

export interface EvaluationReport {
  evaluation_run_id: number;
  dataset_id: number;
  evaluator_name: EvaluatorType;
  evaluator_version: string;
  overall: ReportMetrics;
  models: ModelReport[];
  bad_cases: BadCase[];
  unassessed_cases: Array<{
    task_id: string;
    requested_model: string;
    reason: string;
  }>;
  samples: ReportSample[];
}

export interface EvaluationResponse {
  evaluation_run_id: number;
  evaluator_name: string;
  evaluator_version: string;
  evaluated_tasks: number;
  skipped_tasks: Array<{ task_id: string; reason: string }>;
}
