"""Sidebar controls for configuring benchmarks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from rag_ops.models import BenchmarkConfig


@dataclass(frozen=True)
class SidebarSelections:
    """Materialized sidebar choices."""

    config: BenchmarkConfig
    n_combos: int
    hybrid_requires_dense: bool

def _credential_options(
    credentials: list[dict[str, Any]],
    *,
    provider: str,
) -> list[dict[str, str]]:
    return [item for item in credentials if str(item.get("provider", "")).lower() == provider]


def render_sidebar(st, *, api_mode_enabled: bool = False, api_client=None) -> SidebarSelections:
    """Render the sidebar and return the chosen benchmark settings."""
    credentials: list[dict[str, Any]] = []
    identity: dict[str, Any] | None = None
    if api_mode_enabled and api_client is not None:
        try:
            identity = api_client.get_me()
        except Exception:
            identity = None
        try:
            credentials = list(api_client.list_provider_credentials().get("items", []))
        except Exception:
            credentials = []

    with st.sidebar:
        st.markdown("## RAG-OPS")
        st.caption("Configure your benchmark below")
        if api_mode_enabled:
            st.caption("API-backed admin mode is enabled")
            if identity:
                st.caption(
                    f"Workspace: `{identity.get('workspace_slug', '-')}` | "
                    f"Role: `{identity.get('role', '-')}`"
                )

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

        api_keys: dict[str, str] = {}
        credential_bindings: dict[str, str] = {}
        if api_mode_enabled and (embed_openai_small or embed_openai_large or embed_cohere):
            st.info(
                "API mode uses server-side provider credentials or environment variables. "
                "Sidebar API keys are only used in standalone local mode."
            )
            with st.expander("Provider Credentials", expanded=False):
                if api_client is None:
                    st.caption("API client unavailable.")
                elif identity and identity.get("role") not in {"workspace_admin", "workspace_owner"}:
                    st.caption("Provider credential management is available to workspace admins only.")
                else:
                    if credentials:
                        for item in credentials:
                            col1, col2, col3 = st.columns([3, 1, 1])
                            col1.caption(
                                f"{item.get('label')} | {item.get('provider')} | key `{item.get('key_id')}`"
                            )
                            if item.get("needs_rotation"):
                                col1.warning("Needs rotation")
                            if col2.button("Rotate", key=f"rotate-{item['id']}"):
                                api_client.rotate_provider_credential(str(item["id"]))
                                st.rerun()
                            if col3.button("Delete", key=f"delete-{item['id']}"):
                                api_client.delete_provider_credential(str(item["id"]))
                                st.rerun()
                    else:
                        st.caption("No workspace credentials saved yet.")

                    with st.form("create-provider-credential", clear_on_submit=True):
                        provider = st.selectbox("Provider", ["openai", "cohere"], key="provider-create")
                        label = st.text_input("Label", key="provider-label")
                        secret = st.text_input("Secret", type="password", key="provider-secret")
                        if st.form_submit_button("Save Credential"):
                            if provider and label.strip() and secret.strip():
                                api_client.create_provider_credential(
                                    provider=provider,
                                    label=label.strip(),
                                    secret=secret.strip(),
                                )
                                st.rerun()

                    openai_credentials = _credential_options(credentials, provider="openai")
                    if embed_openai_small or embed_openai_large:
                        openai_labels = ["Use server env/default"] + [
                            f"{item['label']} ({item['key_id']})" for item in openai_credentials
                        ]
                        selected_openai = st.selectbox("OpenAI Credential", openai_labels, key="openai-credential")
                        if selected_openai != "Use server env/default":
                            selected_index = openai_labels.index(selected_openai) - 1
                            credential_bindings["openai"] = str(openai_credentials[selected_index]["id"])

                    cohere_credentials = _credential_options(credentials, provider="cohere")
                    if embed_cohere:
                        cohere_labels = ["Use server env/default"] + [
                            f"{item['label']} ({item['key_id']})" for item in cohere_credentials
                        ]
                        selected_cohere = st.selectbox("Cohere Credential", cohere_labels, key="cohere-credential")
                        if selected_cohere != "Use server env/default":
                            selected_index = cohere_labels.index(selected_cohere) - 1
                            credential_bindings["cohere"] = str(cohere_credentials[selected_index]["id"])
        elif embed_openai_small or embed_openai_large:
            api_keys["openai"] = st.text_input(
                "OpenAI API Key",
                type="password",
                placeholder="sk-...",
            ).strip()
        if not api_mode_enabled and embed_cohere:
            api_keys["cohere"] = st.text_input(
                "Cohere API Key",
                type="password",
                placeholder="...",
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
        if api_mode_enabled:
            st.info(
                "API mode uses the server-side cache and always persists run artifacts for result loading."
            )
            enable_disk_cache = True
            persist_run_artifacts = True
        else:
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
            credential_bindings=credential_bindings,
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
