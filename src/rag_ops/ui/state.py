"""Session-state helpers for the Streamlit app."""

SESSION_DEFAULTS = {
    "data_loaded": False,
    "documents": [],
    "queries": [],
    "ground_truth": {},
    "results_df": None,
    "per_query_results": None,
    "run_artifacts": None,
}


def init_session_state(st) -> None:
    """Initialize session state keys."""
    for key, default in SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default


def store_loaded_data(st, documents, queries, ground_truth) -> None:
    """Persist loaded dataset in the current session."""
    st.session_state.documents = documents
    st.session_state.queries = queries
    st.session_state.ground_truth = ground_truth
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
    st.session_state.results_df = None
    st.session_state.per_query_results = None
    st.session_state.run_artifacts = None


def store_benchmark_results(st, results_df, per_query_results, run_artifacts=None) -> None:
    """Store benchmark results and artifact metadata."""
    st.session_state.results_df = results_df
    st.session_state.per_query_results = per_query_results
    st.session_state.run_artifacts = run_artifacts

