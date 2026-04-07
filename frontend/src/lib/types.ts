export type Tone = "neutral" | "success" | "warning" | "danger" | "info";

export interface ConnectionSettings {
  apiBaseUrl: string;
  authToken: string;
  workspaceSlug: string;
}

export interface HealthReport {
  status: string;
  service: string;
  environment: string;
  timestamp: string;
  components: Record<string, { status: string; detail: string; latency_ms?: number | null }>;
}

export interface Identity {
  auth_mode: string;
  user_id: string | null;
  user_email: string | null;
  user_name: string | null;
  workspace_id: string;
  workspace_slug: string;
  workspace_name: string;
  role: string;
}

export interface DatasetVersion {
  id: string;
  dataset_id: string;
  version_number: number;
  schema_version: string;
  fingerprint: string;
  doc_count: number;
  query_count: number;
  created_at: string;
  documents?: Array<{ doc_id: string; source: string; content: string }>;
  queries?: Array<{ query_id: string; query: string; relevant_doc_ids: string[] }>;
}

export interface DatasetSummary {
  id: string;
  workspace_id: string;
  name: string;
  current_fingerprint: string;
  created_at: string;
  updated_at: string;
  version_count: number;
  latest_version: DatasetVersion | null;
  versions?: DatasetVersion[];
}

export interface BenchmarkConfigPayload {
  id: string;
  workspace_id: string;
  name: string;
  fingerprint: string;
  config: {
    chunker_names: string[];
    embedder_names: string[];
    retriever_names: string[];
    top_k: number;
    combination_count?: number;
  };
  created_at: string;
}

export interface RunSummary {
  id: string;
  workspace_id: string;
  dataset_version_id: string;
  benchmark_config_id: string;
  status: string;
  credential_bindings: Record<string, string>;
  attempt_count: number;
  latest_stage: string;
  latest_progress_pct: number;
  error_summary: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  cancel_requested_at: string | null;
  queue_backend?: string;
}

export interface RunResultRow {
  chunker: string;
  embedder: string;
  retriever: string;
  "precision@k": number;
  "recall@k": number;
  mrr: number;
  "ndcg@k": number;
  "map@k": number;
  "hit_rate@k": number;
  latency_ms: number;
  num_chunks: number;
  avg_chunk_size: number;
  error: string;
  config_label: string;
  run_id?: string;
  metric_value?: number;
}

export interface RunResultsPayload {
  run_id: string;
  items: RunResultRow[];
  per_query_results: Record<string, Array<Record<string, unknown>>>;
}

export interface RunArtifactsPayload {
  run_id: string;
  items: Array<{
    id: string;
    benchmark_run_id: string;
    kind: string;
    uri: string;
    format: string;
    size_bytes: number | null;
    created_at: string;
  }>;
  bundle: {
    run_id: string;
    directory: string;
    summary_json: string;
    results_csv: string;
    results_json: string;
    per_query_json: string;
  } | null;
}

export interface ProviderCredential {
  id: string;
  workspace_id: string;
  provider: string;
  label: string;
  key_id: string;
  needs_rotation: boolean;
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface ComparePayload {
  metric: string;
  runs: RunSummary[];
  items: RunResultRow[];
  best_by_run: Record<string, RunResultRow | null>;
  winner: RunResultRow | null;
}

export interface LeaderboardPayload {
  metric: string;
  limit: number;
  items: RunResultRow[];
}
