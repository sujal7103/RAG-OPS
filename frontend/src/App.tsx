import { Route, Routes } from "react-router-dom";
import { useEffect, useState } from "react";
import { AppShell } from "./components/AppShell";
import { RagOpsApi } from "./lib/api";
import type { ConnectionSettings, Identity } from "./lib/types";
import { OverviewPage } from "./pages/OverviewPage";
import { DatasetsPage } from "./pages/DatasetsPage";
import { RunsPage } from "./pages/RunsPage";
import { CredentialsPage } from "./pages/CredentialsPage";
import { ReportsPage } from "./pages/ReportsPage";

const CONNECTION_KEY = "rag_ops_react_connection";

function loadConnectionSettings(): ConnectionSettings {
  const envDefault = (import.meta.env.VITE_RAG_OPS_API_BASE_URL as string | undefined) || "";
  const fallback: ConnectionSettings = {
    apiBaseUrl: envDefault || "http://localhost:8000",
    authToken: "",
    workspaceSlug: "personal",
  };

  const raw = window.localStorage.getItem(CONNECTION_KEY);
  if (!raw) return fallback;

  try {
    const parsed = JSON.parse(raw) as Partial<ConnectionSettings>;
    return {
      apiBaseUrl: parsed.apiBaseUrl || fallback.apiBaseUrl,
      authToken: parsed.authToken || "",
      workspaceSlug: parsed.workspaceSlug || fallback.workspaceSlug,
    };
  } catch {
    return fallback;
  }
}

export default function App() {
  const [connection, setConnection] = useState<ConnectionSettings>(loadConnectionSettings);
  const [identity, setIdentity] = useState<Identity | null>(null);

  useEffect(() => {
    window.localStorage.setItem(CONNECTION_KEY, JSON.stringify(connection));
  }, [connection]);

  useEffect(() => {
    let cancelled = false;
    const api = new RagOpsApi(connection);
    api
      .me()
      .then((payload) => {
        if (!cancelled) {
          setIdentity(payload);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setIdentity(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [connection.apiBaseUrl, connection.authToken, connection.workspaceSlug]);

  return (
    <AppShell identity={identity} connection={connection} onConnectionChange={setConnection}>
      <Routes>
        <Route path="/" element={<OverviewPage connection={connection} />} />
        <Route path="/datasets" element={<DatasetsPage connection={connection} />} />
        <Route path="/runs" element={<RunsPage connection={connection} />} />
        <Route path="/credentials" element={<CredentialsPage connection={connection} />} />
        <Route path="/reports" element={<ReportsPage connection={connection} />} />
      </Routes>
    </AppShell>
  );
}
