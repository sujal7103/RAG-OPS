import { useEffect, useState } from "react";
import { EmptyState } from "../components/EmptyState";
import { Panel } from "../components/Panel";
import { StatusPill } from "../components/StatusPill";
import { ApiError, RagOpsApi } from "../lib/api";
import type { ComparePayload, ConnectionSettings, LeaderboardPayload, RunSummary } from "../lib/types";
import { compactId, formatDate, formatMetric } from "../lib/utils";

interface ReportsPageProps {
  connection: ConnectionSettings;
}

const reportMetrics = ["recall@k", "precision@k", "mrr", "ndcg@k", "map@k", "hit_rate@k", "latency_ms"];

export function ReportsPage({ connection }: ReportsPageProps) {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [leaderboard, setLeaderboard] = useState<LeaderboardPayload | null>(null);
  const [comparison, setComparison] = useState<ComparePayload | null>(null);
  const [metric, setMetric] = useState("recall@k");
  const [leftRunId, setLeftRunId] = useState("");
  const [rightRunId, setRightRunId] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const api = new RagOpsApi(connection);
    async function load() {
      try {
        const [runPayload, leaderboardPayload] = await Promise.all([
          api.listRuns(),
          api.leaderboard(metric, 12),
        ]);
        const completedRuns = runPayload.items.filter((item) => item.status === "completed");
        setRuns(completedRuns);
        setLeaderboard(leaderboardPayload);
        if (!leftRunId && completedRuns[0]) {
          setLeftRunId(completedRuns[0].id);
        }
        if (!rightRunId && completedRuns[1]) {
          setRightRunId(completedRuns[1].id);
        }
      } catch (caught) {
        setError(caught instanceof ApiError ? caught.message : "Could not load reporting data.");
      }
    }
    void load();
  }, [connection.apiBaseUrl, connection.authToken, connection.workspaceSlug, metric]);

  async function runComparison() {
    if (!leftRunId || !rightRunId || leftRunId === rightRunId) {
      setError("Choose two different completed runs to compare.");
      return;
    }

    try {
      const api = new RagOpsApi(connection);
      const payload = await api.compareRuns([leftRunId, rightRunId], metric);
      setComparison(payload);
      setError("");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not compare runs.");
    }
  }

  return (
    <div className="page-grid">
      <div className="page-header">
        <div>
          <div className="eyebrow">Reports</div>
          <h2>Compare completed runs and surface the best retrieval patterns across time.</h2>
        </div>
      </div>

      {error ? <div className="alert danger">{error}</div> : null}

      <div className="two-column">
        <Panel
          title="Workspace Leaderboard"
          eyebrow="Historical winners"
          actions={
            <select value={metric} onChange={(event) => setMetric(event.target.value)}>
              {reportMetrics.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          }
        >
          {leaderboard?.items.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Run</th>
                    <th>Config</th>
                    <th>{metric}</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {leaderboard.items.map((item, index) => (
                    <tr key={`${item.run_id || "row"}-${index}`}>
                      <td>{compactId(item.run_id || "—")}</td>
                      <td>{item.chunker} · {item.embedder} · {item.retriever}</td>
                      <td>{formatMetric(item.metric_value ?? item[metric as keyof typeof item])}</td>
                      <td>{formatDate((item as { run_created_at?: string }).run_created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState title="No completed runs" description="Complete at least one benchmark run to generate a historical leaderboard." />
          )}
        </Panel>

        <Panel title="Run Comparison" eyebrow="Head-to-head">
          {runs.length >= 2 ? (
            <div className="form-stack">
              <label>
                <span>Left run</span>
                <select value={leftRunId} onChange={(event) => setLeftRunId(event.target.value)}>
                  <option value="">Select a run</option>
                  {runs.map((run) => (
                    <option key={run.id} value={run.id}>
                      {compactId(run.id)} · {formatDate(run.created_at)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>Right run</span>
                <select value={rightRunId} onChange={(event) => setRightRunId(event.target.value)}>
                  <option value="">Select a run</option>
                  {runs.map((run) => (
                    <option key={run.id} value={run.id}>
                      {compactId(run.id)} · {formatDate(run.created_at)}
                    </option>
                  ))}
                </select>
              </label>
              <button className="button primary" onClick={() => void runComparison()}>
                Compare runs
              </button>

              {comparison?.winner ? (
                <div className="winner-card">
                  <div className="eyebrow">Winner</div>
                  <h3>{compactId(comparison.winner.run_id || "run")}</h3>
                  <p>
                    {comparison.winner.chunker} · {comparison.winner.embedder} ·{" "}
                    {comparison.winner.retriever}
                  </p>
                  <StatusPill status="completed" />
                </div>
              ) : null}
            </div>
          ) : (
            <EmptyState title="Need two completed runs" description="Launch and finish at least two runs to unlock historical comparison." />
          )}
        </Panel>
      </div>

      <Panel title="Comparison Detail" eyebrow="Per-row output">
        {comparison?.items.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Chunker</th>
                  <th>Embedder</th>
                  <th>Retriever</th>
                  <th>{comparison.metric}</th>
                </tr>
              </thead>
              <tbody>
                {comparison.items.map((item, index) => (
                  <tr key={`${item.run_id || "compare"}-${index}`}>
                    <td>{compactId(item.run_id || "—")}</td>
                    <td>{item.chunker}</td>
                    <td>{item.embedder}</td>
                    <td>{item.retriever}</td>
                    <td>{formatMetric(item.metric_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No comparison loaded" description="Pick two completed runs and compare them on a chosen metric." />
        )}
      </Panel>
    </div>
  );
}
