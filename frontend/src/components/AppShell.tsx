import { NavLink } from "react-router-dom";
import type { PropsWithChildren } from "react";
import type { ConnectionSettings, Identity } from "../lib/types";

interface AppShellProps extends PropsWithChildren {
  identity: Identity | null;
  connection: ConnectionSettings;
  onConnectionChange: (next: ConnectionSettings) => void;
}

const navItems = [
  { to: "/", label: "Overview" },
  { to: "/datasets", label: "Datasets" },
  { to: "/runs", label: "Runs" },
  { to: "/credentials", label: "Credentials" },
  { to: "/reports", label: "Reports" },
];

export function AppShell({ children, identity, connection, onConnectionChange }: AppShellProps) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-kicker">Retrieval Release Control</div>
          <h1>RAG-OPS</h1>
          <p>
            The product console for benchmark runs, workspace credentials, and retrieval
            reporting.
          </p>
        </div>

        <nav className="nav-list">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`.trim()}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footnote">
          <div className="footnote-label">Workspace</div>
          <div className="footnote-value">{identity?.workspace_name || "Unresolved"}</div>
          <div className="footnote-meta">
            {identity?.role || "No role"} · {identity?.auth_mode || "Not connected"}
          </div>
        </div>
      </aside>

      <div className="main-shell">
        <header className="topbar">
          <div>
            <div className="topbar-kicker">React product UI</div>
            <div className="topbar-title">RAG release management without notebook sprawl</div>
          </div>

          <div className="connection-card">
            <label>
              <span>API URL</span>
              <input
                value={connection.apiBaseUrl}
                onChange={(event) =>
                  onConnectionChange({ ...connection, apiBaseUrl: event.target.value })
                }
                placeholder="http://localhost:8000"
              />
            </label>
            <label>
              <span>Workspace Slug</span>
              <input
                value={connection.workspaceSlug}
                onChange={(event) =>
                  onConnectionChange({ ...connection, workspaceSlug: event.target.value })
                }
                placeholder="personal"
              />
            </label>
            <label>
              <span>Bearer Token</span>
              <input
                value={connection.authToken}
                onChange={(event) =>
                  onConnectionChange({ ...connection, authToken: event.target.value })
                }
                placeholder="Optional in dev mode"
                type="password"
              />
            </label>
          </div>
        </header>

        <main className="page-content">{children}</main>
      </div>
    </div>
  );
}
