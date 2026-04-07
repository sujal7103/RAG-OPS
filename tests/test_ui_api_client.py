"""Tests for the Streamlit API client helpers."""

from __future__ import annotations

import json
from pathlib import Path

from rag_ops.ui.api_client import load_run_outputs


def test_load_run_outputs_reads_saved_artifacts(tmp_path: Path, monkeypatch):
    """Saved run outputs should load back into the UI-friendly structures."""
    runs_dir = tmp_path / "runs"
    run_id = "run-test-123"
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True)

    (run_dir / "results.json").write_text(
        json.dumps(
            [
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
                }
            ]
        )
    )
    (run_dir / "per_query.json").write_text(
        json.dumps(
            {
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
            }
        )
    )
    (run_dir / "summary.json").write_text(json.dumps({"run_id": run_id}))
    (run_dir / "results.csv").write_text("chunker,embedder,retriever\n")

    monkeypatch.setenv("RAG_OPS_RUNS_DIR", str(runs_dir))

    results_df, per_query_results, artifact = load_run_outputs(run_id)

    assert len(results_df) == 1
    assert per_query_results["Fixed Size + MiniLM + Dense"][0]["query_id"] == "q1"
    assert artifact is not None
    assert artifact.run_id == run_id
    assert artifact.results_json.endswith("results.json")
