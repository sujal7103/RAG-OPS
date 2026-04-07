"""Tiny HTTP server for exposing worker metrics."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from rag_ops.metrics_registry import get_metrics_registry


class _MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return

        payload = get_metrics_registry().render_prometheus().encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "text/plain; version=0.0.4")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):  # noqa: A003 - BaseHTTPRequestHandler API
        return


def start_metrics_http_server(*, host: str, port: int) -> ThreadingHTTPServer:
    """Start a background metrics HTTP server and return the bound server."""
    server = ThreadingHTTPServer((host, port), _MetricsHandler)
    thread = Thread(target=server.serve_forever, name="rag-ops-metrics", daemon=True)
    thread.start()
    return server
