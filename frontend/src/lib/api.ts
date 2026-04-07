import type {
  BenchmarkConfigPayload,
  ComparePayload,
  ConnectionSettings,
  DatasetSummary,
  HealthReport,
  Identity,
  LeaderboardPayload,
  ProviderCredential,
  RunArtifactsPayload,
  RunResultsPayload,
  RunSummary,
} from "./types";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status = 500) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export class RagOpsApi {
  constructor(private readonly settings: ConnectionSettings) {}

  private headers(json = true): HeadersInit {
    const headers: Record<string, string> = {
      Accept: "application/json",
    };
    if (json) {
      headers["Content-Type"] = "application/json";
    }
    if (this.settings.authToken.trim()) {
      headers.Authorization = `Bearer ${this.settings.authToken.trim()}`;
    }
    if (this.settings.workspaceSlug.trim()) {
      headers["x-rag-ops-workspace-slug"] = this.settings.workspaceSlug.trim();
    }
    return headers;
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${this.settings.apiBaseUrl.replace(/\/$/, "")}${path}`, {
      ...init,
      headers: {
        ...this.headers(!(init?.body instanceof FormData)),
        ...(init?.headers || {}),
      },
    });

    if (response.status === 204) {
      return undefined as T;
    }

    let payload: unknown = null;
    const text = await response.text();
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        payload = text;
      }
    }

    if (!response.ok) {
      const detail =
        typeof payload === "object" && payload !== null && "detail" in payload
          ? String((payload as { detail?: unknown }).detail)
          : response.statusText || "Request failed";
      throw new ApiError(detail, response.status);
    }

    return payload as T;
  }

  root() {
    return this.request<{ service: string; environment: string; status: string }>("/");
  }

  health() {
    return this.request<HealthReport>("/health");
  }

  ready() {
    return this.request<HealthReport>("/ready");
  }

  me() {
    return this.request<Identity>("/v1/me");
  }

  listDatasets() {
    return this.request<{ items: DatasetSummary[] }>("/v1/datasets");
  }

  getDataset(datasetId: string) {
    return this.request<DatasetSummary>(`/v1/datasets/${datasetId}`);
  }

  createDataset(payload: {
    name: string;
    documents: Array<{ doc_id: string; content: string; source: string }>;
    queries: Array<{ query_id: string; query: string }>;
    ground_truth: Record<string, string[]>;
  }) {
    return this.request<DatasetSummary>("/v1/datasets", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  listConfigs() {
    return this.request<{ items: BenchmarkConfigPayload[] }>("/v1/configs");
  }

  createConfig(payload: {
    name: string;
    chunker_names: string[];
    embedder_names: string[];
    retriever_names: string[];
    top_k: number;
  }) {
    return this.request<BenchmarkConfigPayload>("/v1/configs", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  listRuns() {
    return this.request<{ items: RunSummary[] }>("/v1/runs");
  }

  getRun(runId: string) {
    return this.request<RunSummary>(`/v1/runs/${runId}`);
  }

  createRun(payload: {
    dataset_version_id: string;
    benchmark_config_id: string;
    credential_bindings: Record<string, string>;
  }) {
    return this.request<RunSummary>("/v1/runs", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  cancelRun(runId: string) {
    return this.request<RunSummary>(`/v1/runs/${runId}/cancel`, {
      method: "POST",
    });
  }

  getRunResults(runId: string) {
    return this.request<RunResultsPayload>(`/v1/runs/${runId}/results`);
  }

  getRunArtifacts(runId: string) {
    return this.request<RunArtifactsPayload>(`/v1/runs/${runId}/artifacts`);
  }

  compareRuns(runIds: string[], metric: string) {
    return this.request<ComparePayload>("/v1/runs/compare", {
      method: "POST",
      body: JSON.stringify({ run_ids: runIds, metric }),
    });
  }

  leaderboard(metric: string, limit = 12) {
    const query = new URLSearchParams({ metric, limit: String(limit) });
    return this.request<LeaderboardPayload>(`/v1/reports/leaderboard?${query.toString()}`);
  }

  listProviderCredentials() {
    return this.request<{ items: ProviderCredential[] }>("/v1/provider-credentials");
  }

  createProviderCredential(payload: { provider: string; label: string; secret: string }) {
    return this.request<ProviderCredential>("/v1/provider-credentials", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  rotateProviderCredential(id: string) {
    return this.request<ProviderCredential>(`/v1/provider-credentials/${id}/rotate`, {
      method: "POST",
    });
  }

  deleteProviderCredential(id: string) {
    return this.request<void>(`/v1/provider-credentials/${id}`, {
      method: "DELETE",
    });
  }
}
