import { useEffect, useState } from "react";
import { EmptyState } from "../components/EmptyState";
import { Panel } from "../components/Panel";
import { ApiError, RagOpsApi } from "../lib/api";
import { demoDataset } from "../data/demoDataset";
import type { ConnectionSettings, DatasetSummary } from "../lib/types";
import { formatDate } from "../lib/utils";

interface DatasetsPageProps {
  connection: ConnectionSettings;
}

interface ParsedQuery {
  query_id: string;
  query: string;
  relevant_doc_ids: string[];
}

export function DatasetsPage({ connection }: DatasetsPageProps) {
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<DatasetSummary | null>(null);
  const [datasetName, setDatasetName] = useState("Uploaded Dataset");
  const [docFiles, setDocFiles] = useState<FileList | null>(null);
  const [queryFile, setQueryFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function refreshDatasets(pickId?: string) {
    const api = new RagOpsApi(connection);
    const payload = await api.listDatasets();
    setDatasets(payload.items);
    const nextId = pickId || selectedDataset?.id || payload.items[0]?.id;
    if (nextId) {
      const detail = await api.getDataset(nextId);
      setSelectedDataset(detail);
    } else {
      setSelectedDataset(null);
    }
  }

  useEffect(() => {
    void refreshDatasets();
  }, [connection.apiBaseUrl, connection.authToken, connection.workspaceSlug]);

  async function parseDocumentFiles(files: FileList) {
    return Promise.all(
      Array.from(files).map(async (file) => ({
        doc_id: file.name.replace(/\.[^.]+$/, ""),
        content: await file.text(),
        source: file.name,
      })),
    );
  }

  async function parseQueryFile(file: File): Promise<ParsedQuery[]> {
    const raw = await file.text();
    const parsed = JSON.parse(raw) as ParsedQuery[];
    return parsed;
  }

  async function createDatasetFromPayload(payload: {
    name: string;
    documents: Array<{ doc_id: string; content: string; source: string }>;
    queries: Array<{ query_id: string; query: string }>;
    ground_truth: Record<string, string[]>;
  }) {
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const api = new RagOpsApi(connection);
      const created = await api.createDataset(payload);
      setSuccess(`Created dataset ${created.name} with version ${created.latest_version?.version_number || 1}.`);
      await refreshDatasets(created.id);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not create dataset.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDemoDataset() {
    await createDatasetFromPayload(demoDataset);
  }

  async function handleUploadSubmit() {
    if (!docFiles || !queryFile) {
      setError("Choose both document files and a queries JSON file.");
      return;
    }

    try {
      const documents = await parseDocumentFiles(docFiles);
      const parsedQueries = await parseQueryFile(queryFile);
      await createDatasetFromPayload({
        name: datasetName.trim() || "Uploaded Dataset",
        documents,
        queries: parsedQueries.map(({ query_id, query }) => ({ query_id, query })),
        ground_truth: Object.fromEntries(
          parsedQueries.map((item) => [item.query_id, item.relevant_doc_ids]),
        ),
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not parse uploaded files.");
    }
  }

  return (
    <div className="page-grid">
      <div className="page-header">
        <div>
          <div className="eyebrow">Datasets</div>
          <h2>Version your retrieval corpora instead of overwriting them.</h2>
        </div>
      </div>

      {error ? <div className="alert danger">{error}</div> : null}
      {success ? <div className="alert success">{success}</div> : null}

      <div className="two-column">
        <Panel title="Create Dataset" eyebrow="Ingest">
          <div className="form-stack">
            <button className="button primary" onClick={() => void handleDemoDataset()} disabled={submitting}>
              Create Demo Dataset
            </button>
            <label>
              <span>Dataset name</span>
              <input value={datasetName} onChange={(event) => setDatasetName(event.target.value)} />
            </label>
            <label>
              <span>Documents (.txt, .md)</span>
              <input type="file" multiple accept=".txt,.md" onChange={(event) => setDocFiles(event.target.files)} />
            </label>
            <label>
              <span>Queries JSON</span>
              <input type="file" accept=".json,application/json" onChange={(event) => setQueryFile(event.target.files?.[0] || null)} />
            </label>
            <button className="button secondary" onClick={() => void handleUploadSubmit()} disabled={submitting}>
              {submitting ? "Saving dataset…" : "Upload dataset"}
            </button>
            <p className="helper-copy">
              `queries.json` should be an array with `query_id`, `query`, and `relevant_doc_ids`.
            </p>
          </div>
        </Panel>

        <Panel title="Saved Datasets" eyebrow="Catalog">
          {datasets.length ? (
            <div className="stack-list">
              {datasets.map((dataset) => (
                <button
                  key={dataset.id}
                  className={`dataset-row ${selectedDataset?.id === dataset.id ? "active" : ""}`.trim()}
                  onClick={() => void refreshDatasets(dataset.id)}
                >
                  <div>
                    <div className="list-row-title">{dataset.name}</div>
                    <div className="list-row-meta">
                      {dataset.version_count} versions · updated {formatDate(dataset.updated_at)}
                    </div>
                  </div>
                  <div className="mini-chip">{dataset.latest_version?.doc_count || 0} docs</div>
                </button>
              ))}
            </div>
          ) : (
            <EmptyState title="No datasets yet" description="Create the demo dataset or upload your own corpus and query file to start benchmarking." />
          )}
        </Panel>
      </div>

      <Panel title="Dataset Detail" eyebrow="Selected dataset">
        {selectedDataset ? (
          <div className="detail-grid">
            <div className="detail-column">
              <h3>{selectedDataset.name}</h3>
              <p>
                Fingerprint <code>{selectedDataset.current_fingerprint}</code>
              </p>
              <p>{selectedDataset.version_count} total versions</p>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Version</th>
                    <th>Documents</th>
                    <th>Queries</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {(selectedDataset.versions || []).map((version) => (
                    <tr key={version.id}>
                      <td>v{version.version_number}</td>
                      <td>{version.doc_count}</td>
                      <td>{version.query_count}</td>
                      <td>{formatDate(version.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <EmptyState title="No dataset selected" description="Pick a dataset from the catalog to inspect its versions." />
        )}
      </Panel>
    </div>
  );
}
