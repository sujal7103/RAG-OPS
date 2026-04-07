"""Main Streamlit application entrypoint."""

from __future__ import annotations

import time

from rag_ops.runner import run_benchmark
from rag_ops.settings import (
    ensure_directory,
    get_default_cache_dir,
    get_default_runs_dir,
    get_settings,
)
from rag_ops.ui.api_client import (
    ApiClientError,
    get_streamlit_api_client,
    load_run_outputs,
)
from rag_ops.ui.data_views import render_data_loader, render_loaded_data_summary
from rag_ops.ui.results import render_results
from rag_ops.ui.sidebar import render_sidebar
from rag_ops.ui.state import init_session_state, store_benchmark_results
from rag_ops.ui.styles import apply_page_style, render_header


TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled"}


def _create_api_config_name(config) -> str:
    return (
        f"UI Config | {len(config.chunker_names)}c/"
        f"{len(config.embedder_names)}e/{len(config.retriever_names)}r | top_k={config.top_k}"
    )


def _run_benchmark_via_api(st, api_client, config) -> None:
    active_settings = get_settings()
    if not st.session_state.dataset_version_id:
        st.error("No persisted dataset version is available for API mode.")
        return

    with st.status("Submitting benchmark run to API...", expanded=True) as status_box:
        progress_bar = st.progress(0)
        status_text = st.empty()

        config_payload = api_client.create_config(
            name=_create_api_config_name(config),
            chunker_names=list(config.chunker_names),
            embedder_names=list(config.embedder_names),
            retriever_names=list(config.retriever_names),
            top_k=config.top_k,
        )
        run_payload = api_client.create_run(
            dataset_version_id=st.session_state.dataset_version_id,
            benchmark_config_id=str(config_payload["id"]),
        )
        run_id = str(run_payload["id"])
        st.session_state.run_id = run_id
        st.session_state.run_status = str(run_payload.get("status", "queued"))

        progress_bar.progress(int(run_payload.get("latest_progress_pct", 0) or 0))
        status_text.markdown(f"**{run_payload.get('latest_stage', 'queued')}**")

        while True:
            run_payload = api_client.get_run(run_id)
            current_status = str(run_payload.get("status", "queued"))
            st.session_state.run_status = current_status

            progress_pct = int(run_payload.get("latest_progress_pct", 0) or 0)
            latest_stage = str(run_payload.get("latest_stage", current_status))
            progress_bar.progress(min(max(progress_pct, 0), 100))
            status_text.markdown(f"**{latest_stage}**")

            if current_status in TERMINAL_RUN_STATUSES:
                break
            time.sleep(active_settings.ui_api_poll_interval_seconds)

        if current_status != "completed":
            if current_status == "cancelled":
                status_box.update(label="Benchmark cancelled", state="error", expanded=True)
                st.warning("The benchmark run was cancelled before completion.")
            else:
                status_box.update(label="Benchmark failed", state="error", expanded=True)
                st.error(run_payload.get("error_summary", "The benchmark run failed."))
            return

        results_df, per_query_results, run_artifacts = load_run_outputs(run_id)
        store_benchmark_results(
            st,
            results_df,
            per_query_results,
            run_artifacts=run_artifacts,
            run_id=run_id,
            run_status=current_status,
        )
        progress_bar.progress(100)
        status_box.update(label="Benchmark complete!", state="complete", expanded=False)
    st.rerun()


def run_app() -> None:
    """Render and run the Streamlit app."""
    import streamlit as st

    get_settings()
    apply_page_style(st)
    init_session_state(st)
    api_client = get_streamlit_api_client()
    api_mode_enabled = api_client is not None
    sidebar = render_sidebar(st, api_mode_enabled=api_mode_enabled)

    render_header(st)

    if not st.session_state.data_loaded:
        render_data_loader(st, api_client=api_client)
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
    if (
        not api_mode_enabled
        and ("OpenAI Small" in config.embedder_names or "OpenAI Large" in config.embedder_names)
        and not config.api_keys.get("openai")
    ):
        warnings.append(
            "Enter your **OpenAI API key** in the sidebar or set `OPENAI_API_KEY` / Streamlit secrets."
        )
        can_run = False
    if not api_mode_enabled and "Cohere" in config.embedder_names and not config.api_keys.get("cohere"):
        warnings.append(
            "Enter your **Cohere API key** in the sidebar or set `COHERE_API_KEY` / Streamlit secrets."
        )
        can_run = False

    for warning in warnings:
        st.warning(warning)

    if sidebar.hybrid_requires_dense:
        st.info("Hybrid retrieval requires Vector Search, so Dense retrieval was enabled automatically.")
    if api_mode_enabled and (
        "OpenAI Small" in config.embedder_names
        or "OpenAI Large" in config.embedder_names
        or "Cohere" in config.embedder_names
    ):
        st.info(
            "API mode requires provider credentials or environment variables on the API/worker "
            "service for cloud embedding models."
        )

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
            try:
                if api_mode_enabled:
                    _run_benchmark_via_api(st, api_client, config)
                else:
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
                            run_status="completed",
                        )
                        progress_bar.progress(100)
                        status_box.update(label="Benchmark complete!", state="complete", expanded=False)
                    st.rerun()
            except ApiClientError as exc:
                st.error(str(exc))
            except FileNotFoundError as exc:
                st.error(str(exc))

    if st.session_state.results_df is not None:
        render_results(
            st,
            st.session_state.results_df,
            st.session_state.per_query_results,
            config.top_k,
            run_artifacts=st.session_state.run_artifacts,
        )
