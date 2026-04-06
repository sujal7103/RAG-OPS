"""Persistence helpers for benchmark run artifacts."""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from rag_ops.models import BenchmarkArtifacts

DEFAULT_RUNS_DIRNAME = ".rag_ops_runs"


def get_runs_dir(base_dir: str | Path | None = None) -> Path:
    """Resolve the run-artifact directory."""
    configured = base_dir or os.getenv("RAG_OPS_RUNS_DIR") or DEFAULT_RUNS_DIRNAME
    path = Path(configured)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _json_default(value: Any) -> Any:
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def persist_benchmark_run(
    results_rows: Sequence[Mapping[str, Any]],
    per_query_results: Mapping[str, Sequence[Mapping[str, Any]]],
    metadata: Mapping[str, Any],
    runs_dir: str | Path | None = None,
) -> BenchmarkArtifacts:
    """Save aggregate and per-query artifacts for a completed run."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = metadata.get("run_id", f"run_{timestamp}")

    directory = get_runs_dir(runs_dir) / run_id
    directory.mkdir(parents=True, exist_ok=True)

    results_csv = directory / "results.csv"
    results_json = directory / "results.json"
    per_query_json = directory / "per_query.json"
    summary_json = directory / "summary.json"

    fieldnames = sorted({key for row in results_rows for key in row.keys()})
    with results_csv.open("w", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()
        for row in results_rows:
            writer.writerow(row)

    results_json.write_text(json.dumps(list(results_rows), indent=2, default=_json_default))
    per_query_json.write_text(json.dumps(per_query_results, indent=2, default=_json_default))
    summary_json.write_text(json.dumps(dict(metadata), indent=2, default=_json_default))

    return BenchmarkArtifacts(
        run_id=run_id,
        directory=str(directory),
        summary_json=str(summary_json),
        results_csv=str(results_csv),
        results_json=str(results_json),
        per_query_json=str(per_query_json),
    )

