"""Sidebar controls for configuring benchmarks."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from rag_ops.models import BenchmarkConfig


@dataclass(frozen=True)
class SidebarSelections:
    """Materialized sidebar choices."""

    config: BenchmarkConfig
    n_combos: int
    hybrid_requires_dense: bool


def _secret_value(st, secret_name: str, env_name: str) -> str:
    env_value = os.getenv(env_name, "").strip()
    if env_value:
        return env_value

    try:
        return str(st.secrets.get(secret_name, "")).strip()
    except Exception:
        # Streamlit raises when no secrets file exists. Treat that as "not configured".
        return ""


def render_sidebar(st) -> SidebarSelections:
    """Render the sidebar and return the chosen benchmark settings."""
    with st.sidebar:
        st.markdown("## RAG-OPS")
        st.caption("Configure your benchmark below")

        st.markdown(
            '<div class="sidebar-section"><div class="sidebar-section-title">Chunking Strategies</div>',
            unsafe_allow_html=True,
        )
        chunker_fixed = st.checkbox(
            "Fixed Size",
            value=True,
            help="Simple character-count splits with overlap",
        )
        chunker_recursive = st.checkbox(
            "Recursive",
            value=True,
            help="Smart splits by paragraphs, then sentences",
        )
        chunker_semantic = st.checkbox(
            "Semantic",
            value=False,
            help="Groups sentences by meaning similarity",
        )
        chunker_docaware = st.checkbox(
            "Document-Aware",
            value=False,
            help="Respects markdown headings and code blocks",
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            '<div class="sidebar-section"><div class="sidebar-section-title">Embedding Models</div>',
            unsafe_allow_html=True,
        )
        embed_minilm = st.checkbox(
            "MiniLM",
            value=True,
            help="Fast, 384-dim, runs locally for free",
        )
        embed_bge = st.checkbox(
            "BGE Small",
            value=False,
            help="More accurate, 384-dim, runs locally for free",
        )
        embed_openai_small = st.checkbox(
            "OpenAI Small",
            value=False,
            help="text-embedding-3-small (API key required)",
        )
        embed_openai_large = st.checkbox(
            "OpenAI Large",
            value=False,
            help="text-embedding-3-large (API key required)",
        )
        embed_cohere = st.checkbox(
            "Cohere",
            value=False,
            help="embed-english-v3.0 (API key required)",
        )
        st.markdown("</div>", unsafe_allow_html=True)

        default_openai_key = _secret_value(st, "OPENAI_API_KEY", "OPENAI_API_KEY")
        default_cohere_key = _secret_value(st, "COHERE_API_KEY", "COHERE_API_KEY")
        api_keys: dict[str, str] = {}
        if embed_openai_small or embed_openai_large:
            api_keys["openai"] = st.text_input(
                "OpenAI API Key",
                type="password",
                placeholder="sk-...",
                value=default_openai_key,
            ).strip()
        if embed_cohere:
            api_keys["cohere"] = st.text_input(
                "Cohere API Key",
                type="password",
                placeholder="...",
                value=default_cohere_key,
            ).strip()

        st.markdown(
            '<div class="sidebar-section"><div class="sidebar-section-title">Retrieval Methods</div>',
            unsafe_allow_html=True,
        )
        ret_dense = st.checkbox(
            "Vector Search",
            value=True,
            help="Dense cosine similarity via FAISS or numpy fallback",
        )
        ret_sparse = st.checkbox(
            "Keyword Search (BM25)",
            value=True,
            help="Classic term-frequency ranking",
        )
        ret_hybrid = st.checkbox(
            "Hybrid",
            value=False,
            help="Combines vector + keyword with rank fusion",
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            '<div class="sidebar-section"><div class="sidebar-section-title">Settings</div>',
            unsafe_allow_html=True,
        )
        top_k = st.slider("Top-K results to retrieve", min_value=1, max_value=20, value=5)
        enable_disk_cache = st.toggle(
            "Enable disk cache",
            value=True,
            help="Reuse chunk and embedding artifacts between benchmark runs.",
        )
        persist_run_artifacts = st.toggle(
            "Persist run artifacts",
            value=True,
            help="Save benchmark summaries, CSV, and per-query JSON for later comparison.",
        )
        st.markdown("</div>", unsafe_allow_html=True)

        chunker_names = []
        if chunker_fixed:
            chunker_names.append("Fixed Size")
        if chunker_recursive:
            chunker_names.append("Recursive")
        if chunker_semantic:
            chunker_names.append("Semantic")
        if chunker_docaware:
            chunker_names.append("Document-Aware")

        embedder_names = []
        if embed_minilm:
            embedder_names.append("MiniLM")
        if embed_bge:
            embedder_names.append("BGE Small")
        if embed_openai_small:
            embedder_names.append("OpenAI Small")
        if embed_openai_large:
            embedder_names.append("OpenAI Large")
        if embed_cohere:
            embedder_names.append("Cohere")

        retriever_names = []
        if ret_dense:
            retriever_names.append("Dense")
        if ret_sparse:
            retriever_names.append("Sparse")
        hybrid_requires_dense = ret_hybrid and not ret_dense
        if hybrid_requires_dense:
            retriever_names = ["Dense", *retriever_names]
        if ret_hybrid:
            retriever_names.append("Hybrid")

        config = BenchmarkConfig(
            chunker_names=tuple(chunker_names),
            embedder_names=tuple(embedder_names),
            retriever_names=tuple(dict.fromkeys(retriever_names)),
            top_k=top_k,
            api_keys=api_keys,
            enable_disk_cache=enable_disk_cache,
            persist_run_artifacts=persist_run_artifacts,
        )
        st.markdown(
            f'<div class="combo-pill">{config.combination_count} combination'
            f'{"s" if config.combination_count != 1 else ""} to test</div>',
            unsafe_allow_html=True,
        )

    return SidebarSelections(
        config=config,
        n_combos=config.combination_count,
        hybrid_requires_dense=hybrid_requires_dense,
    )
