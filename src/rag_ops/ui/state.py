"""Session-state helpers for the Streamlit app."""

SESSION_DEFAULTS = {
    "data_loaded": False,
    "documents": [],
    "queries": [],
    "ground_truth": {},
    "dataset_id": None,
    "dataset_version_id": None,
    "dataset_name": None,
    "run_id": None,
    "run_status": None,
    "results_df": None,
    "per_query_results": None,
    "run_artifacts": None,
}


def init_session_state(st) -> None:
    """Initialize session state keys."""
    for key, default in SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default


def store_loaded_data(
    st,
    documents,
    queries,
    ground_truth,
    *,
    dataset_id=None,
    dataset_version_id=None,
    dataset_name=None,
) -> None:
    """Persist loaded dataset in the current session."""
    st.session_state.documents = documents
    st.session_state.queries = queries
    st.session_state.ground_truth = ground_truth
    st.session_state.dataset_id = dataset_id
    st.session_state.dataset_version_id = dataset_version_id
    st.session_state.dataset_name = dataset_name
    st.session_state.run_id = None
    st.session_state.run_status = None
    st.session_state.data_loaded = True
    st.session_state.results_df = None
    st.session_state.per_query_results = None
    st.session_state.run_artifacts = None


def reset_loaded_data(st) -> None:
    """Clear loaded dataset and benchmark results."""
    st.session_state.data_loaded = False
    st.session_state.documents = []
    st.session_state.queries = []
    st.session_state.ground_truth = {}
    st.session_state.dataset_id = None
    st.session_state.dataset_version_id = None
    st.session_state.dataset_name = None
    st.session_state.run_id = None
    st.session_state.run_status = None
    st.session_state.results_df = None
    st.session_state.per_query_results = None
    st.session_state.run_artifacts = None


def store_benchmark_results(
    st,
    results_df,
    per_query_results,
    run_artifacts=None,
    *,
    run_id=None,
    run_status="completed",
) -> None:
    """Store benchmark results and artifact metadata."""
    st.session_state.run_id = run_id
    st.session_state.run_status = run_status
    st.session_state.results_df = results_df
    st.session_state.per_query_results = per_query_results
    st.session_state.run_artifacts = run_artifacts
