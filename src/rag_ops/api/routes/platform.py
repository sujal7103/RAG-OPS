"""Versioned service endpoints for datasets, configs, and runs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from rag_ops.api.dependencies import get_platform_repository
from rag_ops.models import (
    BenchmarkConfig,
    normalize_documents,
    normalize_ground_truth,
    normalize_queries,
)
from rag_ops.repositories.platform import PlatformRepository
from rag_ops.services.benchmark_runs import enqueue_benchmark_run
from rag_ops.services.run_state import RunStateStore
from rag_ops.validation import (
    ValidationError,
    validate_benchmark_configuration,
    validate_documents,
    validate_queries,
)

router = APIRouter(prefix="/v1", tags=["platform"])


class DocumentInput(BaseModel):
    """Input payload for a dataset document."""

    doc_id: str
    content: str
    source: str = ""


class QueryInput(BaseModel):
    """Input payload for a dataset query."""

    query_id: str
    query: str


class DatasetCreateRequest(BaseModel):
    """Create a persisted dataset version."""

    name: str = Field(..., min_length=1)
    documents: list[DocumentInput]
    queries: list[QueryInput]
    ground_truth: dict[str, list[str]]


class ConfigCreateRequest(BaseModel):
    """Persist a benchmark configuration."""

    name: str = Field(..., min_length=1)
    chunker_names: list[str]
    embedder_names: list[str]
    retriever_names: list[str]
    top_k: int = Field(..., gt=0)


class RunCreateRequest(BaseModel):
    """Queue a benchmark run."""

    dataset_version_id: str
    benchmark_config_id: str


def _attach_live_progress(
    run_payload: dict[str, object],
    settings,
) -> dict[str, object]:
    state_store = RunStateStore(settings)
    live = state_store.get_progress(str(run_payload["id"]))
    if not live:
        return run_payload
    merged = dict(run_payload)
    merged["latest_progress_pct"] = live.get("progress_pct", run_payload["latest_progress_pct"])
    merged["latest_stage"] = live.get("stage", run_payload["latest_stage"])
    return merged


@router.get("/datasets")
def list_datasets(repo: PlatformRepository = Depends(get_platform_repository)):
    """List all persisted datasets."""
    return {"items": repo.list_datasets()}


@router.post("/datasets", status_code=status.HTTP_201_CREATED)
def create_dataset(
    payload: DatasetCreateRequest,
    repo: PlatformRepository = Depends(get_platform_repository),
):
    """Persist a dataset and its first or next version."""
    try:
        documents = normalize_documents([item.model_dump() for item in payload.documents])
        queries = normalize_queries([item.model_dump() for item in payload.queries])
        ground_truth = normalize_ground_truth(payload.ground_truth)
        validate_documents(documents)
        validate_queries(queries, ground_truth, [document.doc_id for document in documents])
        return repo.create_dataset(
            name=payload.name.strip(),
            documents=documents,
            queries=queries,
            ground_truth=ground_truth,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/datasets/{dataset_id}")
def get_dataset(dataset_id: str, repo: PlatformRepository = Depends(get_platform_repository)):
    """Return one dataset and all of its versions."""
    try:
        return repo.get_dataset(dataset_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/configs")
def list_configs(repo: PlatformRepository = Depends(get_platform_repository)):
    """List persisted benchmark configs."""
    return {"items": repo.list_configs()}


@router.post("/configs", status_code=status.HTTP_201_CREATED)
def create_config(
    payload: ConfigCreateRequest,
    repo: PlatformRepository = Depends(get_platform_repository),
):
    """Persist a benchmark configuration."""
    try:
        validate_benchmark_configuration(
            payload.chunker_names,
            payload.embedder_names,
            payload.retriever_names,
            payload.top_k,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    config = BenchmarkConfig(
        chunker_names=tuple(payload.chunker_names),
        embedder_names=tuple(payload.embedder_names),
        retriever_names=tuple(payload.retriever_names),
        top_k=payload.top_k,
    )
    config_json = {
        "chunker_names": list(config.chunker_names),
        "embedder_names": list(config.embedder_names),
        "retriever_names": list(config.retriever_names),
        "top_k": config.top_k,
        "combination_count": config.combination_count,
    }
    return repo.create_config(name=payload.name.strip(), config_json=config_json)


@router.get("/configs/{config_id}")
def get_config(config_id: str, repo: PlatformRepository = Depends(get_platform_repository)):
    """Return one benchmark config."""
    try:
        return repo.get_config(config_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/runs")
def list_runs(repo: PlatformRepository = Depends(get_platform_repository)):
    """List benchmark runs."""
    return {"items": [_attach_live_progress(item, repo.settings) for item in repo.list_runs()]}


@router.post("/runs", status_code=status.HTTP_201_CREATED)
def create_run(payload: RunCreateRequest, repo: PlatformRepository = Depends(get_platform_repository)):
    """Create a queued benchmark run."""
    try:
        run_payload = repo.create_run(
            dataset_version_id=payload.dataset_version_id,
            benchmark_config_id=payload.benchmark_config_id,
        )
        queue_backend = enqueue_benchmark_run(str(run_payload["id"]), repo.settings)
        run_payload["queue_backend"] = queue_backend
        return run_payload
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/runs/{run_id}")
def get_run(run_id: str, repo: PlatformRepository = Depends(get_platform_repository)):
    """Return one benchmark run."""
    try:
        return _attach_live_progress(repo.get_run(run_id), repo.settings)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: str, repo: PlatformRepository = Depends(get_platform_repository)):
    """Request cancellation for a queued or running benchmark run."""
    try:
        run_payload = repo.request_cancel(run_id)
        state_store = RunStateStore(repo.settings)
        state_store.request_cancel(run_id)
        return _attach_live_progress(run_payload, repo.settings)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/runs/{run_id}/results")
def get_run_results(run_id: str, repo: PlatformRepository = Depends(get_platform_repository)):
    """Return persisted aggregate and per-query results for a run."""
    try:
        return repo.get_run_results(run_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/runs/{run_id}/artifacts")
def get_run_artifacts(run_id: str, repo: PlatformRepository = Depends(get_platform_repository)):
    """Return persisted artifact metadata for a run."""
    try:
        return repo.list_run_artifacts(run_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
