"""Embedding model wrappers."""

from __future__ import annotations

import os
from typing import Callable, Mapping

import numpy as np


class EmbedderDependencyError(ImportError):
    """Raised when an optional embedder dependency is not installed."""


_models: dict[str, object] = {}


def _normalize_embeddings(embeddings: np.ndarray) -> np.ndarray:
    array = np.array(embeddings, dtype=np.float32)
    if array.size == 0:
        return array
    norms = np.linalg.norm(array, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return array / norms


def _get_st_model(model_name: str):
    """Lazy-load and cache a sentence-transformers model."""
    if model_name not in _models:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError as exc:  # pragma: no cover - exercised via tests
            raise EmbedderDependencyError(
                "sentence-transformers is required for local embedding models. "
                "Install project dependencies to use MiniLM or BGE."
            ) from exc
        _models[model_name] = SentenceTransformer(model_name)
    return _models[model_name]


def embed_minilm(texts: list[str], is_query: bool = False) -> np.ndarray:
    """all-MiniLM-L6-v2 — fast, 384 dimensions, free and local."""
    if not texts:
        return np.empty((0, 0), dtype=np.float32)
    model = _get_st_model("all-MiniLM-L6-v2")
    embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    return _normalize_embeddings(embeddings)


def embed_bge(texts: list[str], is_query: bool = False) -> np.ndarray:
    """BAAI/bge-small-en-v1.5 — accurate, 384 dimensions, free and local."""
    if not texts:
        return np.empty((0, 0), dtype=np.float32)
    model = _get_st_model("BAAI/bge-small-en-v1.5")
    prepared_texts = texts
    if is_query:
        prepared_texts = [
            f"Represent this sentence for searching relevant passages: {text}" for text in texts
        ]
    embeddings = model.encode(prepared_texts, show_progress_bar=False, normalize_embeddings=True)
    return _normalize_embeddings(embeddings)


def embed_openai(
    texts: list[str],
    api_key: str,
    model: str = "text-embedding-3-small",
    is_query: bool = False,
) -> np.ndarray:
    """OpenAI embedding models via API."""
    if not texts:
        return np.empty((0, 0), dtype=np.float32)
    if not api_key:
        raise ValueError("An OpenAI API key is required for OpenAI embeddings.")

    try:
        import openai  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised via tests
        raise EmbedderDependencyError(
            "openai is required for OpenAI embeddings. Install project dependencies first."
        ) from exc

    client = openai.OpenAI(api_key=api_key)
    all_embeddings = []
    batch_size = 100
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        response = client.embeddings.create(input=batch, model=model)
        all_embeddings.extend(item.embedding for item in response.data)
    return _normalize_embeddings(np.array(all_embeddings, dtype=np.float32))


def embed_cohere(texts: list[str], api_key: str, is_query: bool = False) -> np.ndarray:
    """Cohere embed-english-v3.0 via API."""
    if not texts:
        return np.empty((0, 0), dtype=np.float32)
    if not api_key:
        raise ValueError("A Cohere API key is required for Cohere embeddings.")

    try:
        import cohere  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised via tests
        raise EmbedderDependencyError(
            "cohere is required for Cohere embeddings. Install project dependencies first."
        ) from exc

    client = cohere.Client(api_key)
    input_type = "search_query" if is_query else "search_document"

    all_embeddings = []
    batch_size = 96
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        response = client.embed(texts=batch, model="embed-english-v3.0", input_type=input_type)
        all_embeddings.extend(response.embeddings)
    return _normalize_embeddings(np.array(all_embeddings, dtype=np.float32))


EMBEDDERS: dict[str, dict[str, object]] = {
    "MiniLM": {"fn": embed_minilm, "needs_api_key": None},
    "BGE Small": {"fn": embed_bge, "needs_api_key": None},
    "OpenAI Small": {
        "fn": lambda texts, api_key, is_query=False: embed_openai(
            texts,
            api_key,
            "text-embedding-3-small",
            is_query,
        ),
        "needs_api_key": "openai",
    },
    "OpenAI Large": {
        "fn": lambda texts, api_key, is_query=False: embed_openai(
            texts,
            api_key,
            "text-embedding-3-large",
            is_query,
        ),
        "needs_api_key": "openai",
    },
    "Cohere": {"fn": embed_cohere, "needs_api_key": "cohere"},
}


def embed_texts(
    texts: list[str],
    embedder_name: str,
    api_keys: Mapping[str, str] | None = None,
    is_query: bool = False,
) -> np.ndarray:
    """Embed texts using the specified model."""
    api_keys = api_keys or {}
    info = EMBEDDERS[embedder_name]
    fn: Callable[..., np.ndarray] = info["fn"]  # type: ignore[assignment]
    key_name = info["needs_api_key"]

    if key_name:
        api_key = api_keys.get(str(key_name), "")
        if not api_key:
            env_name = "OPENAI_API_KEY" if str(key_name) == "openai" else "COHERE_API_KEY"
            api_key = os.getenv(env_name, "").strip()
        return fn(texts, api_key=api_key, is_query=is_query)
    return fn(texts, is_query=is_query)
