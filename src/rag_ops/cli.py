"""CLI entrypoint for running benchmarks without Streamlit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rag_ops.data_loading import load_local_data, load_sample_data
from rag_ops.runner import run_benchmark
from rag_ops.settings import ensure_directory, get_default_cache_dir, get_default_runs_dir


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a RAG-OPS benchmark from the command line.")
    parser.add_argument("--sample", action="store_true", help="Use built-in sample data.")
    parser.add_argument("--docs-dir", type=str, help="Directory containing .txt or .md documents.")
    parser.add_argument("--queries-file", type=str, help="Path to queries.json.")
    parser.add_argument("--chunkers", nargs="+", default=["Fixed Size", "Recursive"])
    parser.add_argument("--embedders", nargs="+", default=["MiniLM"])
    parser.add_argument("--retrievers", nargs="+", default=["Dense", "Sparse"])
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--openai-api-key", type=str, default="")
    parser.add_argument("--cohere-api-key", type=str, default="")
    parser.add_argument("--no-cache", action="store_true", help="Disable disk caching.")
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Do not save run artifacts to disk.",
    )
    return parser.parse_args()


def _load_inputs(args: argparse.Namespace):
    if args.sample:
        return load_sample_data()
    if not args.docs_dir or not args.queries_file:
        raise SystemExit("Use --sample or provide both --docs-dir and --queries-file.")

    document_paths = sorted(
        [
            path
            for path in Path(args.docs_dir).iterdir()
            if path.is_file() and path.suffix.lower() in {".txt", ".md"}
        ]
    )
    return load_local_data(document_paths, args.queries_file)


def main() -> None:
    args = _parse_args()
    documents, queries, ground_truth = _load_inputs(args)

    captured_artifact = {"value": None}

    def on_artifact(artifact) -> None:
        captured_artifact["value"] = artifact

    results_df, _ = run_benchmark(
        documents=documents,
        queries=queries,
        ground_truth=ground_truth,
        chunker_names=args.chunkers,
        embedder_names=args.embedders,
        retriever_names=args.retrievers,
        top_k=args.top_k,
        api_keys={"openai": args.openai_api_key, "cohere": args.cohere_api_key},
        enable_disk_cache=not args.no_cache,
        cache_dir=ensure_directory(get_default_cache_dir()),
        persist_run_artifacts=not args.no_persist,
        runs_dir=ensure_directory(get_default_runs_dir()),
        artifact_callback=on_artifact,
    )

    if hasattr(results_df, "to_json"):
        print(results_df.to_json(orient="records", indent=2))
    else:
        print(json.dumps(results_df.to_records(), indent=2))

    if captured_artifact["value"] is not None:
        print(f"Artifacts saved to {captured_artifact['value'].directory}")


if __name__ == "__main__":
    main()

