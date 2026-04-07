import { useEffect, useState } from "react";
import { EmptyState } from "../components/EmptyState";
import { MetricCard } from "../components/MetricCard";
import { Panel } from "../components/Panel";
import { ProgressBar } from "../components/ProgressBar";
import { StatusPill } from "../components/StatusPill";
import { ApiError, RagOpsApi } from "../lib/api";
import type { ConnectionSettings, DatasetSummary, HealthReport, Identity, RunSummary } from "../lib/types";
import { compactId, formatDate, groupCountByStatus } from "../lib/utils";

interface OverviewPageProps {
  connection: ConnectionSettings;
}

export function OverviewPage({ connection }: OverviewPageProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");
  const [health, setHealth] = useState<HealthReport | null>(null);
  const [ready, setReady] = useState<HealthReport | null>(null);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);

  useEffect(() => {
    let cancelled = false;
    const api = new RagOpsApi(connection);

    async function load() {
      setLoading(true);
      setError("");
      try {
        const [healthPayload, readyPayload, identityPayload, datasetPayload, runPayload] =
          await Promise.all([
            api.health(),
            api.ready(),
            api.me(),
            api.listDatasets(),
            api.listRuns(),
          ]);
        if (!cancelled) {
          setHealth(healthPayload);
          setReady(readyPayload);
          setIdentity(identityPayload);
          setDatasets(datasetPayload.items);
          setRuns(runPayload.items);
        }
      } catch (caught) {
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught.message : "Could not connect to the API.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [connection.apiBaseUrl, connection.authToken, connection.workspaceSlug]);

  const runStatusCounts = groupCountByStatus(runs);
  const totalVersions = datasets.reduce((sum, item) => sum + item.version_count, 0);
  const recentRuns = runs.slice(0, 5);

  return (
    <div className="page-grid">
      <section className="hero-panel">
        <div className="hero-copy">
          <div className="hero-kicker">React product console</div>
          <h2>Ship retrieval changes with context, history, and visible operational risk.</h2>
          <p>
            This frontend is now the customer-facing surface for datasets, benchmark execution,
            credentials, and retrieval reporting. Streamlit can stay internal.
          </p>
        </div>
        <div className="hero-badges">
          <div className="hero-badge">
            <span>Service</span>
            <strong>{health?.service || "RAG-OPS"}</strong>
          </div>
          <div className="hero-badge">
            <span>Environment</span>
            <strong>{health?.environment || "unknown"}</strong>
          </div>
          <div className="hero-badge">
            <span>Workspace</span>
            <strong>{identity?.workspace_slug || connection.workspaceSlug}</strong>
          </div>
        </div>
      </section>

      {error ? <div className="alert danger">{error}</div> : null}

      <section className="metric-grid">
        <MetricCard label="Datasets" value={String(datasets.length)} hint={`${totalVersions} total versions`} />
        <MetricCard label="Runs" value={String(runs.length)} hint={`${runStatusCounts.completed || 0} completed`} />
        <MetricCard label="Running" value={String((runStatusCounts.running || 0) + (runStatusCounts.retrying || 0))} hint="active benchmark execution" />
        <MetricCard label="Workspace Role" value={identity?.role || "unknown"} hint={identity?.user_email || "connect the API"} />
      </section>

      <div className="two-column">
        <Panel title="Readiness" eyebrow="Platform health">
          {loading ? (
            <div className="loading-copy">Checking API, database, Redis, and warmup state…</div>
          ) : ready ? (
            <div className="stack-list">
              {Object.entries(ready.components).map(([name, component]) => (
                <div key={name} className="list-row">
                  <div>
                    <div className="list-row-title">{name}</div>
                    <div className="list-row-meta">{component.detail}</div>
                  </div>
                  <div className="status-cluster">
                    <StatusPill status={component.status} />
                    {typeof component.latency_ms === "number" ? (
                      <span className="micro-copy">{component.latency_ms.toFixed(1)} ms</span>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No readiness data" description="Connect the frontend to a reachable API." />
          )}
        </Panel>

        <Panel title="Recent Runs" eyebrow="Execution pulse">
          {recentRuns.length ? (
            <div className="stack-list">
              {recentRuns.map((run) => (
                <div key={run.id} className="run-card slim">
                  <div className="run-card-head">
                    <div>
                      <div className="list-row-title">Run {compactId(run.id)}</div>
                      <div className="list-row-meta">{formatDate(run.created_at)}</div>
                    </div>
                    <StatusPill status={run.status} />
                  </div>
                  <div className="run-stage">{run.latest_stage}</div>
                  <ProgressBar value={run.latest_progress_pct} />
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No runs yet" description="Start with a dataset, create a benchmark run, and come back here for the operating picture." />
          )}
        </Panel>
      </div>

      <Panel title="Latest Datasets" eyebrow="Versioned corpora">
        {datasets.length ? (
          <div className="card-grid">
            {datasets.slice(0, 6).map((dataset) => (
              <article key={dataset.id} className="dataset-card">
                <div className="dataset-title-row">
                  <h3>{dataset.name}</h3>
                  <span className="mini-chip">v{dataset.latest_version?.version_number || 0}</span>
                </div>
                <p>{dataset.latest_version?.doc_count || 0} docs · {dataset.latest_version?.query_count || 0} queries</p>
                <div className="micro-copy">Updated {formatDate(dataset.updated_at)}</div>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState title="No datasets" description="Use the Datasets page to create a demo dataset or upload your own document/query pairs." />
        )}
      </Panel>
    </div>
  );
}
