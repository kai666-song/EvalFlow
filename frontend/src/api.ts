import type {
  DatasetDetail,
  DatasetListResponse,
  EvaluationReport,
  EvaluationResponse,
  EvaluationRun,
  EvaluationRunListResponse,
  EvaluatorType,
} from "./types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ??
  "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    let message = `请求失败（HTTP ${response.status}）`;

    try {
      const body = (await response.json()) as {
        detail?: string;
      };
      message = body.detail ?? message;
    } catch {
      // 保留通用错误信息。
    }

    throw new ApiError(message, response.status);
  }

  return response.json() as Promise<T>;
}

export const api = {
  listDatasets: () => request<DatasetListResponse>("/datasets"),

  getDataset: (datasetId: number) =>
    request<DatasetDetail>(`/datasets/${datasetId}`),

  listRuns: (limit = 50) =>
    request<EvaluationRunListResponse>(
      `/evaluation-runs?limit=${limit}`,
    ),

  getRun: (runId: number) =>
    request<EvaluationRun>(`/evaluation-runs/${runId}`),

  createRun: (payload: {
    dataset_id: number;
    models: string[];
    evaluator: EvaluatorType;
    max_concurrency: number;
  }) =>
    request<EvaluationRun>("/evaluation-runs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  startRun: (runId: number) =>
    request<EvaluationRun>(`/evaluation-runs/${runId}/run`, {
      method: "POST",
    }),

  evaluateRun: (runId: number, evaluator: EvaluatorType) =>
    request<EvaluationResponse>(
      `/evaluation-runs/${runId}/evaluate`,
      {
        method: "POST",
        body: JSON.stringify({ evaluator }),
      },
    ),

  getReport: (runId: number, evaluator: EvaluatorType) =>
    request<EvaluationReport>(
      `/evaluation-runs/${runId}/report?evaluator=${evaluator}`,
    ),
};
