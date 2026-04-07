"""API client helpers for the Streamlit admin UI."""

from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from rag_ops.models import BenchmarkArtifacts
from rag_ops.results_frame import build_results_frame
from rag_ops.settings import get_settings


class ApiClientError(RuntimeError):
    """Raised when the admin UI cannot complete an API request."""


class RagOpsApiClient:
    """Small JSON client for the RAG-OPS API."""

    def __init__(self, base_url: str, timeout_seconds: float = 30.0) -> None:
        if not base_url:
            raise ValueError("base_url is required")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def health(self) -> dict[str, Any]:
        """Return the API health payload."""
        return self._request_json("GET", "/health")

    def create_dataset(
        self,
        *,
        name: str,
        documents: list[dict[str, Any]],
        queries: list[dict[str, Any]],
        ground_truth: dict[str, list[str]],
    ) -> dict[str, Any]:
        """Persist a dataset version through the API."""
        return self._request_json(
            "POST",
            "/v1/datasets",
            {
                "name": name,
                "documents": documents,
                "queries": queries,
                "ground_truth": ground_truth,
            },
        )

    def create_config(
        self,
        *,
        name: str,
        chunker_names: list[str],
        embedder_names: list[str],
        retriever_names: list[str],
        top_k: int,
    ) -> dict[str, Any]:
        """Persist a benchmark config through the API."""
        return self._request_json(
            "POST",
            "/v1/configs",
            {
                "name": name,
                "chunker_names": chunker_names,
                "embedder_names": embedder_names,
                "retriever_names": retriever_names,
                "top_k": top_k,
            },
        )

    def create_run(self, *, dataset_version_id: str, benchmark_config_id: str) -> dict[str, Any]:
        """Queue a benchmark run through the API."""
        return self._request_json(
            "POST",
            "/v1/runs",
            {
                "dataset_version_id": dataset_version_id,
                "benchmark_config_id": benchmark_config_id,
            },
        )

    def get_run(self, run_id: str) -> dict[str, Any]:
        """Fetch the latest state for one benchmark run."""
        return self._request_json("GET", f"/v1/runs/{run_id}")

    def get_run_results(self, run_id: str) -> dict[str, Any]:
        """Fetch persisted aggregate and per-query results for a run."""
        return self._request_json("GET", f"/v1/runs/{run_id}/results")

    def get_run_artifacts(self, run_id: str) -> dict[str, Any]:
        """Fetch persisted artifact metadata for a run."""
        return self._request_json("GET", f"/v1/runs/{run_id}/artifacts")

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = None
        headers = {"accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["content-type"] = "application/json"

        req = request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.reason
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    detail = parsed.get("detail", detail)
            except json.JSONDecodeError:
                if raw:
                    detail = raw
            raise ApiClientError(f"{method} {path} failed: {detail}") from exc
        except error.URLError as exc:
            raise ApiClientError(f"Could not reach RAG-OPS API at {self.base_url}") from exc

        if not raw:
            return {}
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ApiClientError(f"{method} {path} returned a non-object response")
        return parsed


def get_streamlit_api_client() -> RagOpsApiClient | None:
    """Return a configured API client when API mode is enabled."""
    settings = get_settings()
    if not settings.api_base_url:
        return None
    return RagOpsApiClient(settings.api_base_url, timeout_seconds=settings.request_timeout_seconds)


def load_run_outputs(
    api_client: RagOpsApiClient,
    run_id: str,
) -> tuple[Any, dict[str, list[dict[str, Any]]], BenchmarkArtifacts | None]:
    """Load persisted run outputs through the API."""
    results_payload = api_client.get_run_results(run_id)
    artifacts_payload = api_client.get_run_artifacts(run_id)

    result_rows = list(results_payload.get("items", []))
    per_query_results = dict(results_payload.get("per_query_results", {}))
    results_df = build_results_frame(result_rows)
    if not results_df.empty:
        results_df = results_df.sort_values("recall@k", ascending=False).reset_index(drop=True)

    artifact = None
    bundle = artifacts_payload.get("bundle")
    if isinstance(bundle, dict):
        artifact = BenchmarkArtifacts(
            run_id=run_id,
            directory=str(bundle.get("directory", "")),
            summary_json=str(bundle.get("summary_json", "")),
            results_csv=str(bundle.get("results_csv", "")),
            results_json=str(bundle.get("results_json", "")),
            per_query_json=str(bundle.get("per_query_json", "")),
        )
    return results_df, per_query_results, artifact
