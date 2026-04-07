"""Tests for the Streamlit API client helpers."""

from __future__ import annotations

from rag_ops.ui.api_client import load_run_outputs


class FakeApiClient:
    def get_run_results(self, run_id: str):
        return {
            "run_id": run_id,
            "items": [
                {
                    "chunker": "Fixed Size",
                    "embedder": "MiniLM",
                    "retriever": "Dense",
                    "precision@k": 1.0,
                    "recall@k": 1.0,
                    "mrr": 1.0,
                    "ndcg@k": 1.0,
                    "map@k": 1.0,
                    "hit_rate@k": 1.0,
                    "latency_ms": 10.0,
                    "num_chunks": 4,
                    "avg_chunk_size": 120.0,
                    "error": "",
                    "config_label": "Fixed Size + MiniLM + Dense",
                }
            ],
            "per_query_results": {
                "Fixed Size + MiniLM + Dense": [
                    {
                        "query_id": "q1",
                        "query": "What is Python?",
                        "retrieved_docs": "doc-1",
                        "relevant_docs": "doc-1",
                        "hit": True,
                        "precision": 1.0,
                        "recall": 1.0,
                        "mrr": 1.0,
                    }
                ]
            },
        }

    def get_run_artifacts(self, run_id: str):
        return {
            "run_id": run_id,
            "items": [],
            "bundle": {
                "run_id": run_id,
                "directory": f"/tmp/{run_id}",
                "summary_json": f"/tmp/{run_id}/summary.json",
                "results_csv": f"/tmp/{run_id}/results.csv",
                "results_json": f"/tmp/{run_id}/results.json",
                "per_query_json": f"/tmp/{run_id}/per_query.json",
            },
        }


def test_load_run_outputs_reads_api_payloads():
    """API result and artifact payloads should load into UI-friendly structures."""
    run_id = "run-test-123"

    results_df, per_query_results, artifact = load_run_outputs(FakeApiClient(), run_id)

    assert len(results_df) == 1
    assert per_query_results["Fixed Size + MiniLM + Dense"][0]["query_id"] == "q1"
    assert artifact is not None
    assert artifact.run_id == run_id
    assert artifact.results_json.endswith("results.json")
