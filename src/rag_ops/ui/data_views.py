"""Data loading and data summary views for the Streamlit app."""

from __future__ import annotations

from rag_ops.models import Document, Query
from rag_ops.ui.api_client import ApiClientError
from rag_ops.data_loading import load_sample_data, load_uploaded_data
from rag_ops.ui.state import reset_loaded_data, store_loaded_data
from rag_ops.validation import ValidationError


def _build_ground_truth_payload(
    queries: list[Query],
    ground_truth: dict[str, set[str]],
) -> dict[str, list[str]]:
    return {
        query.query_id: sorted(ground_truth.get(query.query_id, set()))
        for query in queries
    }


def _persist_dataset_if_needed(
    api_client,
    *,
    name: str,
    documents: list[Document],
    queries: list[Query],
    ground_truth: dict[str, set[str]],
) -> tuple[str | None, str | None]:
    if api_client is None:
        return None, None

    payload = api_client.create_dataset(
        name=name,
        documents=[document.to_mapping() for document in documents],
        queries=[query.to_mapping() for query in queries],
        ground_truth=_build_ground_truth_payload(queries, ground_truth),
    )
    latest_version = payload.get("latest_version") or {}
    return payload.get("id"), latest_version.get("id")


def render_data_loader(st, api_client=None) -> None:
    """Render the first step for loading sample or uploaded data."""
    st.markdown(
        """
        <div class="step-header">
            <div class="step-number">1</div>
            <div class="step-title">Load your data</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown(
            """
            <div class="data-card">
                <h4>Try with sample data</h4>
                <p>10 Python tutorial documents and 15 test queries. Great for a quick demo.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("")
        if st.button("Load Sample Data", type="primary", use_container_width=True):
            try:
                with st.spinner("Loading sample data..."):
                    documents, queries, ground_truth = load_sample_data()
                    dataset_id, dataset_version_id = _persist_dataset_if_needed(
                        api_client,
                        name="Sample Data",
                        documents=documents,
                        queries=queries,
                        ground_truth=ground_truth,
                    )
            except ApiClientError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(str(exc))
            else:
                store_loaded_data(
                    st,
                    documents,
                    queries,
                    ground_truth,
                    dataset_id=dataset_id,
                    dataset_version_id=dataset_version_id,
                    dataset_name="Sample Data",
                )
                st.rerun()

    with col2:
        st.markdown(
            """
            <div class="data-card">
                <h4>Upload your own</h4>
                <p>Upload .txt or .md documents and a queries.json file with ground-truth labels.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("")
        doc_files = st.file_uploader(
            "Documents (.txt, .md)",
            accept_multiple_files=True,
            type=["txt", "md"],
            label_visibility="collapsed",
        )
        queries_file = st.file_uploader(
            "Queries (.json)",
            type=["json"],
            label_visibility="collapsed",
        )
        if doc_files and queries_file:
            if st.button("Load Uploaded Data", use_container_width=True):
                try:
                    with st.spinner("Processing uploaded files..."):
                        documents, queries, ground_truth = load_uploaded_data(doc_files, queries_file)
                        dataset_id, dataset_version_id = _persist_dataset_if_needed(
                            api_client,
                            name="Uploaded Dataset",
                            documents=documents,
                            queries=queries,
                            ground_truth=ground_truth,
                        )
                except (ValidationError, ValueError, TypeError) as exc:
                    st.error(str(exc))
                except ApiClientError as exc:
                    st.error(str(exc))
                else:
                    store_loaded_data(
                        st,
                        documents,
                        queries,
                        ground_truth,
                        dataset_id=dataset_id,
                        dataset_version_id=dataset_version_id,
                        dataset_name="Uploaded Dataset",
                    )
                    st.rerun()

        with st.expander("Expected queries.json format"):
            st.code(
                """[
  {
    "query_id": "q01",
    "query": "Your question here",
    "relevant_doc_ids": ["doc_filename_without_extension"]
  }
]""",
                language="json",
            )


def render_loaded_data_summary(st) -> None:
    """Render a summary and preview of the currently loaded dataset."""
    documents = st.session_state.documents
    queries = st.session_state.queries
    total_chars = sum(len(document.content) for document in documents)

    col1, col2, col3, col4 = st.columns([1, 1, 1, 0.6])
    with col1:
        st.markdown(
            f"""
            <div class="stat-card">
                <div class="stat-value">{len(documents)}</div>
                <div class="stat-label">Documents</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"""
            <div class="stat-card">
                <div class="stat-value">{len(queries)}</div>
                <div class="stat-label">Test Queries</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f"""
            <div class="stat-card">
                <div class="stat-value">{total_chars:,}</div>
                <div class="stat-label">Total Characters</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col4:
        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        if st.button("Change data", type="secondary", use_container_width=True):
            reset_loaded_data(st)
            st.rerun()

    if st.session_state.dataset_version_id:
        st.caption(
            f"Persisted dataset version: `{st.session_state.dataset_version_id}`"
        )

    with st.expander("Preview loaded data", expanded=False):
        tab_docs, tab_queries = st.tabs(["Documents", "Queries"])
        with tab_docs:
            for document in documents[:3]:
                st.markdown(f"**{document.doc_id}**")
                st.text(document.content[:300] + ("..." if len(document.content) > 300 else ""))
                st.markdown("---")
        with tab_queries:
            for query in queries[:5]:
                relevant = st.session_state.ground_truth.get(query.query_id, set())
                st.markdown(f"**{query.query_id}**: {query.query}")
                st.caption(f"Relevant: {', '.join(sorted(relevant))}")
