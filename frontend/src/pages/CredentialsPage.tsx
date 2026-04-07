import { useEffect, useState } from "react";
import { EmptyState } from "../components/EmptyState";
import { Panel } from "../components/Panel";
import { StatusPill } from "../components/StatusPill";
import { ApiError, RagOpsApi } from "../lib/api";
import type { ConnectionSettings, Identity, ProviderCredential } from "../lib/types";
import { formatDate } from "../lib/utils";

interface CredentialsPageProps {
  connection: ConnectionSettings;
}

export function CredentialsPage({ connection }: CredentialsPageProps) {
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [credentials, setCredentials] = useState<ProviderCredential[]>([]);
  const [provider, setProvider] = useState("openai");
  const [label, setLabel] = useState("");
  const [secret, setSecret] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const canManageCredentials =
    identity?.role === "workspace_admin" || identity?.role === "workspace_owner";

  async function refresh() {
    const api = new RagOpsApi(connection);
    const me = await api.me();
    setIdentity(me);
    try {
      const payload = await api.listProviderCredentials();
      setCredentials(payload.items);
      setError("");
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 403) {
        setCredentials([]);
        setError("This workspace role can view the page but cannot manage credentials.");
        return;
      }
      throw caught;
    }
  }

  useEffect(() => {
    void refresh().catch((caught) => {
      setError(caught instanceof ApiError ? caught.message : "Could not load provider credentials.");
    });
  }, [connection.apiBaseUrl, connection.authToken, connection.workspaceSlug]);

  async function handleCreate() {
    if (!label.trim() || !secret.trim()) {
      setError("Provide both a label and secret value.");
      return;
    }
    try {
      const api = new RagOpsApi(connection);
      await api.createProviderCredential({ provider, label: label.trim(), secret: secret.trim() });
      setLabel("");
      setSecret("");
      setSuccess("Credential stored and encrypted successfully.");
      await refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not save credential.");
    }
  }

  async function handleRotate(id: string) {
    try {
      const api = new RagOpsApi(connection);
      await api.rotateProviderCredential(id);
      setSuccess("Credential rotated to the active key.");
      await refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not rotate credential.");
    }
  }

  async function handleDelete(id: string) {
    try {
      const api = new RagOpsApi(connection);
      await api.deleteProviderCredential(id);
      setSuccess("Credential deleted.");
      await refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not delete credential.");
    }
  }

  return (
    <div className="page-grid">
      <div className="page-header">
        <div>
          <div className="eyebrow">Credentials</div>
          <h2>Bind provider keys to the workspace instead of pasting secrets into every run.</h2>
        </div>
      </div>

      {error ? <div className="alert danger">{error}</div> : null}
      {success ? <div className="alert success">{success}</div> : null}

      <div className="two-column">
        <Panel title="Create Credential" eyebrow="Encrypted workspace secret">
          {canManageCredentials ? (
            <div className="form-stack">
              <label>
                <span>Provider</span>
                <select value={provider} onChange={(event) => setProvider(event.target.value)}>
                  <option value="openai">OpenAI</option>
                  <option value="cohere">Cohere</option>
                </select>
              </label>
              <label>
                <span>Label</span>
                <input value={label} onChange={(event) => setLabel(event.target.value)} placeholder="Production OpenAI key" />
              </label>
              <label>
                <span>Secret</span>
                <input value={secret} onChange={(event) => setSecret(event.target.value)} type="password" placeholder="sk-..." />
              </label>
              <button className="button primary" onClick={() => void handleCreate()}>
                Save credential
              </button>
              <p className="helper-copy">
                Active role: <strong>{identity?.role || "unknown"}</strong>. Rotation status is shown per credential.
              </p>
            </div>
          ) : (
            <EmptyState
              title="Admin role required"
              description="Workspace admins and owners can create or rotate provider credentials from this page."
            />
          )}
        </Panel>

        <Panel title="Stored Credentials" eyebrow="Workspace inventory">
          {credentials.length ? (
            <div className="stack-list">
              {credentials.map((credential) => (
                <article key={credential.id} className="credential-card">
                  <div className="run-card-head">
                    <div>
                      <div className="list-row-title">{credential.label}</div>
                      <div className="list-row-meta">
                        {credential.provider} · created {formatDate(credential.created_at)}
                      </div>
                    </div>
                    <StatusPill status={credential.needs_rotation ? "needs_rotation" : "ready"} />
                  </div>
                  <div className="credential-meta">Key ID: {credential.key_id}</div>
                  <div className="run-actions">
                    <button className="button ghost" onClick={() => void handleRotate(credential.id)}>
                      Rotate
                    </button>
                    <button className="button danger-lite" onClick={() => void handleDelete(credential.id)}>
                      Delete
                    </button>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState title="No credentials yet" description="Create at least one provider credential so cloud embedding runs can bind to workspace-managed secrets." />
          )}
        </Panel>
      </div>
    </div>
  );
}
