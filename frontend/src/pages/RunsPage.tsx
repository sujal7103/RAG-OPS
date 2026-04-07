import { useEffect, useState } from "react";
import { EmptyState } from "../components/EmptyState";
import { Panel } from "../components/Panel";
import { ProgressBar } from "../components/ProgressBar";
import { StatusPill } from "../components/StatusPill";
import { ApiError, RagOpsApi } from "../lib/api";
import type {
  ConnectionSettings,
  DatasetSummary,
  ProviderCredential,
  RunArtifactsPayload,
  RunResultsPayload,
  RunSummary,
} from "../lib/types";
import { compactId, formatDate, formatMetric } from "../lib/utils";

interface RunsPageProps {
  connection: ConnectionSettings;
}

const chunkerOptions = ["Fixed Size", "Recursive", "Semantic", "Document-Aware"];
const embedderOptions = ["MiniLM", "BGE Small", "OpenAI Small", "OpenAI Large", "Cohere"];
const retrieverOptions = ["Dense", "Sparse", "Hybrid"];

export function RunsPage({ connection }: RunsPageProps) {
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [credentials, setCredentials] = useState<ProviderCredential[]>([]);
  const [selectedDatasetVersionId, setSelectedDatasetVersionId] = useState("");
  const [topK, setTopK] = useState(5);
  const [chunkers, setChunkers] = useState<string[]>(["Fixed Size", "Recursive"]);
  const [embedders, setEmbedders] = useState<string[]>(["MiniLM"]);
  const [retrievers, setRetrievers] = useState<string[]>(["Dense", "Sparse"]);
  const [credentialBindings, setCredentialBindings] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [selectedRunId, setSelectedRunId] = useState("");
  const [runResults, setRunResults] = useState<RunResultsPayload | null>(null);
  const [runArtifacts, setRunArtifacts] = useState<RunArtifactsPayload | null>(null);

  function updateBinding(provider: string, credentialId: string) {
    setCredentialBindings((current) => {
      const next = { ...current };
      if (credentialId) {
        next[provider] = credentialId;
      } else {
        delete next[provider];
      }
      return next;
    });
  }

  async function refreshRunsAndDatasets() {
    const api = new RagOpsApi(connection);
    const [datasetPayload, runPayload] = await Promise.all([api.listDatasets(), api.listRuns()]);
    setDatasets(datasetPayload.items);
    setRuns(runPayload.items);
    if (!selectedDatasetVersionId && datasetPayload.items[0]?.latest_version?.id) {
      setSelectedDatasetVersionId(datasetPayload.items[0].latest_version.id);
    }
  }

  useEffect(() => {
    let cancelled = false;
    const api = new RagOpsApi(connection);

    async function load() {
      try {
        const [datasetPayload, runPayload] = await Promise.all([api.listDatasets(), api.listRuns()]);
        if (cancelled) return;
        setDatasets(datasetPayload.items);
        setRuns(runPayload.items);
        if (!selectedDatasetVersionId && datasetPayload.items[0]?.latest_version?.id) {
          setSelectedDatasetVersionId(datasetPayload.items[0].latest_version.id);
        }
        try {
          const credentialPayload = await api.listProviderCredentials();
          if (!cancelled) {
            setCredentials(credentialPayload.items);
          }
        } catch {
          if (!cancelled) {
            setCredentials([]);
          }
        }
      } catch (caught) {
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught.message : "Could not load runs.");
        }
      }
    }

    void load();
    const intervalId = window.setInterval(() => {
      void refreshRunsAndDatasets();
    }, 4000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [connection.apiBaseUrl, connection.authToken, connection.workspaceSlug]);

  function toggleSelection(current: string[], option: string) {
    return current.includes(option) ? current.filter((item) => item !== option) : [...current, option];
  }

  async function launchRun() {
    setError("");
    setSuccess("");
    if (!selectedDatasetVersionId) {
      setError("Choose a dataset version before launching a run.");
      return;
    }
    if (!chunkers.length || !embedders.length || !retrievers.length) {
      setError("Pick at least one chunker, embedder, and retriever.");
      return;
    }

    const effectiveBindings: Record<string, string> = {};
    if (embedders.some((item) => item.startsWith("OpenAI")) && credentialBindings.openai) {
      effectiveBindings.openai = credentialBindings.openai;
    }
    if (embedders.includes("Cohere") && credentialBindings.cohere) {
      effectiveBindings.cohere = credentialBindings.cohere;
    }

    try {
      const api = new RagOpsApi(connection);
      const config = await api.createConfig({
        name: `React UI | ${chunkers.length}c/${embedders.length}e/${retrievers.length}r | top_k=${topK}`,
        chunker_names: chunkers,
        embedder_names: embedders,
        retriever_names: retrievers,
        top_k: topK,
      });
      const run = await api.createRun({
        dataset_version_id: selectedDatasetVersionId,
        benchmark_config_id: config.id,
        credential_bindings: effectiveBindings,
      });
      setSuccess(`Queued run ${compactId(run.id)} via ${run.queue_backend || "thread"} backend.`);
      setSelectedRunId(run.id);
      await refreshRunsAndDatasets();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not launch benchmark run.");
    }
  }

  async function inspectRun(runId: string) {
    setSelectedRunId(runId);
    setError("");
    try {
      const api = new RagOpsApi(connection);
      const [resultsPayload, artifactsPayload] = await Promise.all([
        api.getRunResults(runId),
        api.getRunArtifacts(runId),
      ]);
      setRunResults(resultsPayload);
      setRunArtifacts(artifactsPayload);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not inspect run.");
    }
  }

  async function cancelRun(runId: string) {
    try {
      const api = new RagOpsApi(connection);
      await api.cancelRun(runId);
      await refreshRunsAndDatasets();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not cancel run.");
    }
  }

  const visibleResults = runResults?.items || [];

  return (
    <div className="page-grid">
      <div className="page-header">
        <div>
          <div className="eyebrow">Runs</div>
          <h2>Launch benchmark matrices without opening the old admin tool.</h2>
        </div>
      </div>

      {error ? <div className="alert danger">{error}</div> : null}
      {success ? <div className="alert success">{success}</div> : null}

      <div className="two-column">
        <Panel title="Launch Run" eyebrow="Execution setup">
          <div className="form-stack">
            <label>
              <span>Dataset version</span>
              <select value={selectedDatasetVersionId} onChange={(event) => setSelectedDatasetVersionId(event.target.value)}>
                <option value="">Select a dataset version</option>
                {datasets.map((dataset) =>
                  dataset.latest_version ? (
                    <option key={dataset.latest_version.id} value={dataset.latest_version.id}>
                      {dataset.name} · v{dataset.latest_version.version_number}
                    </option>
                  ) : null,
                )}
              </select>
            </label>

            <label>
              <span>Top K</span>
              <input
                type="number"
                min={1}
                max={20}
                value={topK}
                onChange={(event) => setTopK(Number(event.target.value))}
              />
            </label>

            <div className="option-grid">
              <div>
                <div className="field-label">Chunkers</div>
                {chunkerOptions.map((option) => (
                  <label className="checkbox-row" key={option}>
                    <input
                      type="checkbox"
                      checked={chunkers.includes(option)}
                      onChange={() => setChunkers((current) => toggleSelection(current, option))}
                    />
                    <span>{option}</span>
                  </label>
                ))}
              </div>
              <div>
                <div className="field-label">Embedders</div>
                {embedderOptions.map((option) => (
                  <label className="checkbox-row" key={option}>
                    <input
                      type="checkbox"
                      checked={embedders.includes(option)}
                      onChange={() => setEmbedders((current) => toggleSelection(current, option))}
                    />
                    <span>{option}</span>
                  </label>
                ))}
              </div>
              <div>
                <div className="field-label">Retrievers</div>
                {retrieverOptions.map((option) => (
                  <label className="checkbox-row" key={option}>
                    <input
                      type="checkbox"
                      checked={retrievers.includes(option)}
                      onChange={() => setRetrievers((current) => toggleSelection(current, option))}
                    />
                    <span>{option}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="option-grid compact">
              {embedders.some((item) => item.startsWith("OpenAI")) ? (
                <label>
                  <span>OpenAI credential</span>
                  <select
                    value={credentialBindings.openai || ""}
                    onChange={(event) => updateBinding("openai", event.target.value)}
                  >
                    <option value="">Use server default</option>
                    {credentials
                      .filter((item) => item.provider === "openai")
                      .map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.label} ({item.key_id})
                        </option>
                      ))}
                  </select>
                </label>
              ) : null}

              {embedders.includes("Cohere") ? (
                <label>
                  <span>Cohere credential</span>
                  <select
                    value={credentialBindings.cohere || ""}
                    onChange={(event) => updateBinding("cohere", event.target.value)}
                  >
                    <option value="">Use server default</option>
                    {credentials
                      .filter((item) => item.provider === "cohere")
                      .map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.label} ({item.key_id})
                        </option>
                      ))}
                  </select>
                </label>
              ) : null}
            </div>

            <button className="button primary" onClick={() => void launchRun()}>
              Launch benchmark run
            </button>
          </div>
        </Panel>

        <Panel title="Live Runs" eyebrow="Polling every 4 seconds">
          {runs.length ? (
            <div className="stack-list">
              {runs.map((run) => (
                <article key={run.id} className={`run-card ${selectedRunId === run.id ? "selected" : ""}`.trim()}>
                  <div className="run-card-head">
                    <div>
                      <div className="list-row-title">Run {compactId(run.id)}</div>
                      <div className="list-row-meta">{formatDate(run.created_at)}</div>
                    </div>
                    <StatusPill status={run.status} />
                  </div>
                  <div className="run-stage">{run.latest_stage}</div>
                  <ProgressBar value={run.latest_progress_pct} />
                  <div className="run-actions">
                    <button className="button ghost" onClick={() => void inspectRun(run.id)}>
                      Inspect
                    </button>
                    {["queued", "running", "retrying", "cancel_requested"].includes(run.status) ? (
                      <button className="button danger-lite" onClick={() => void cancelRun(run.id)}>
                        Cancel
                      </button>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState title="No runs yet" description="Launch your first matrix from the configuration panel." />
          )}
        </Panel>
      </div>

      <Panel title="Selected Run Output" eyebrow="Inspection">
        {selectedRunId && (visibleResults.length || runArtifacts?.bundle) ? (
          <div className="detail-grid">
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Chunker</th>
                    <th>Embedder</th>
                    <th>Retriever</th>
                    <th>Recall</th>
                    <th>Precision</th>
                    <th>Latency</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleResults.map((row, index) => (
                    <tr key={`${row.config_label}-${index}`}>
                      <td>{row.chunker}</td>
                      <td>{row.embedder}</td>
                      <td>{row.retriever}</td>
                      <td>{formatMetric(row["recall@k"])}</td>
                      <td>{formatMetric(row["precision@k"])}</td>
                      <td>{formatMetric(row.latency_ms, 1)} ms</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {runArtifacts?.bundle ? (
              <div className="artifact-box">
                <h3>Artifact bundle</h3>
                <p><strong>Directory:</strong> {runArtifacts.bundle.directory}</p>
                <p><strong>Summary:</strong> {runArtifacts.bundle.summary_json}</p>
                <p><strong>Results JSON:</strong> {runArtifacts.bundle.results_json}</p>
              </div>
            ) : null}
          </div>
        ) : (
          <EmptyState title="No run selected" description="Inspect a run to view aggregate retrieval results and persisted artifacts." />
        )}
      </Panel>
    </div>
  );
}
