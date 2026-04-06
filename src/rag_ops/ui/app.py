"""Main Streamlit application entrypoint."""

from __future__ import annotations

from rag_ops.runner import run_benchmark
from rag_ops.settings import ensure_directory, get_default_cache_dir, get_default_runs_dir
from rag_ops.ui.data_views import render_data_loader, render_loaded_data_summary
from rag_ops.ui.results import render_results
from rag_ops.ui.sidebar import render_sidebar
from rag_ops.ui.state import init_session_state, store_benchmark_results
from rag_ops.ui.styles import apply_page_style, render_header


def run_app() -> None:
    """Render and run the Streamlit app."""
    import streamlit as st

    apply_page_style(st)
    init_session_state(st)
    sidebar = render_sidebar(st)

    render_header(st)

    if not st.session_state.data_loaded:
        render_data_loader(st)
        return

    render_loaded_data_summary(st)
    st.markdown('<hr class="soft-divider">', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="step-header">
            <div class="step-number">2</div>
            <div class="step-title">Run benchmark</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    config = sidebar.config
    can_run = True
    warnings: list[str] = []
    if not config.chunker_names:
        warnings.append("Select at least one **chunking strategy** in the sidebar.")
        can_run = False
    if not config.embedder_names:
        warnings.append("Select at least one **embedding model** in the sidebar.")
        can_run = False
    if not config.retriever_names:
        warnings.append("Select at least one **retrieval method** in the sidebar.")
        can_run = False
    if ("OpenAI Small" in config.embedder_names or "OpenAI Large" in config.embedder_names) and not config.api_keys.get("openai"):
        warnings.append(
            "Enter your **OpenAI API key** in the sidebar or set `OPENAI_API_KEY` / Streamlit secrets."
        )
        can_run = False
    if "Cohere" in config.embedder_names and not config.api_keys.get("cohere"):
        warnings.append(
            "Enter your **Cohere API key** in the sidebar or set `COHERE_API_KEY` / Streamlit secrets."
        )
        can_run = False

    for warning in warnings:
        st.warning(warning)

    if sidebar.hybrid_requires_dense:
        st.info("Hybrid retrieval requires Vector Search, so Dense retrieval was enabled automatically.")

    if can_run:
        st.markdown(
            f"Ready to test **{sidebar.n_combos}** combinations: "
            f"**{len(config.chunker_names)}** chunker(s) x "
            f"**{len(config.embedder_names)}** embedder(s) x "
            f"**{len(config.retriever_names)}** retriever(s)"
        )

        if st.button(
            f"Run Benchmark ({sidebar.n_combos} combination{'s' if sidebar.n_combos != 1 else ''})",
            type="primary",
            use_container_width=True,
        ):
            captured_artifact = {"value": None}

            def on_artifact(artifact) -> None:
                captured_artifact["value"] = artifact

            with st.status("Running benchmark...", expanded=True) as status_box:
                progress_bar = st.progress(0)
                status_text = st.empty()

                def on_progress(percent: int, message: str) -> None:
                    progress_bar.progress(percent)
                    status_text.markdown(f"**{message}**")

                results_df, per_query_results = run_benchmark(
                    documents=st.session_state.documents,
                    queries=st.session_state.queries,
                    ground_truth=st.session_state.ground_truth,
                    chunker_names=config.chunker_names,
                    embedder_names=config.embedder_names,
                    retriever_names=config.retriever_names,
                    top_k=config.top_k,
                    api_keys=config.api_keys,
                    progress_callback=on_progress,
                    enable_disk_cache=config.enable_disk_cache,
                    cache_dir=ensure_directory(get_default_cache_dir()),
                    persist_run_artifacts=config.persist_run_artifacts,
                    runs_dir=ensure_directory(get_default_runs_dir()),
                    artifact_callback=on_artifact,
                )

                store_benchmark_results(
                    st,
                    results_df,
                    per_query_results,
                    run_artifacts=captured_artifact["value"],
                )
                progress_bar.progress(100)
                status_box.update(label="Benchmark complete!", state="complete", expanded=False)
            st.rerun()

    if st.session_state.results_df is not None:
        render_results(
            st,
            st.session_state.results_df,
            st.session_state.per_query_results,
            config.top_k,
            run_artifacts=st.session_state.run_artifacts,
        )

