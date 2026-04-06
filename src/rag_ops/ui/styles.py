"""Shared page configuration and styling for the Streamlit app."""

PAGE_CONFIG = {
    "page_title": "RAG-OPS",
    "page_icon": "🔬",
    "layout": "wide",
    "initial_sidebar_state": "expanded",
}

APP_CSS = """
<style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    section[data-testid="stSidebar"] {
        background-color: #F7F8FC;
        border-right: 1px solid #E5E7EB;
    }
    section[data-testid="stSidebar"] .stMarkdown h2 {
        color: #1A1A2E;
        font-size: 1.25rem;
        font-weight: 700;
        letter-spacing: -0.02em;
        margin-bottom: 0.25rem;
    }
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: #1A1A2E;
        font-size: 0.95rem;
        font-weight: 600;
        margin-bottom: 0.15rem;
        margin-top: 0.5rem;
    }
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown span,
    section[data-testid="stSidebar"] .stMarkdown label,
    section[data-testid="stSidebar"] label {
        color: #374151 !important;
        font-size: 0.9rem;
    }
    section[data-testid="stSidebar"] hr {
        border-color: #E5E7EB;
        margin: 0.75rem 0;
    }
    .sidebar-section {
        background: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 10px;
        padding: 0.85rem 1rem;
        margin-bottom: 0.75rem;
    }
    .sidebar-section-title {
        font-size: 0.8rem;
        font-weight: 700;
        color: #5B6ABF;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 0.5rem;
    }
    .combo-pill {
        background: linear-gradient(135deg, #5B6ABF, #7C3AED);
        color: white;
        border-radius: 20px;
        padding: 0.6rem 1rem;
        text-align: center;
        font-weight: 700;
        font-size: 1rem;
        margin-top: 0.5rem;
    }
    .app-header {
        text-align: center;
        padding: 1.5rem 0 1rem 0;
    }
    .app-header h1 {
        font-size: 2.2rem;
        font-weight: 800;
        color: #1A1A2E;
        margin-bottom: 0.3rem;
        letter-spacing: -0.03em;
    }
    .app-header .accent {
        background: linear-gradient(135deg, #5B6ABF, #7C3AED);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .app-header p {
        font-size: 1.05rem;
        color: #6B7280;
        max-width: 680px;
        margin: 0 auto;
        line-height: 1.5;
    }
    .stat-card {
        background: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 12px;
        padding: 1.25rem 1rem;
        text-align: center;
        transition: box-shadow 0.2s;
    }
    .stat-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.06);
    }
    .stat-card .stat-value {
        font-size: 2rem;
        font-weight: 800;
        color: #1A1A2E;
        line-height: 1.1;
    }
    .stat-card .stat-label {
        font-size: 0.8rem;
        color: #9CA3AF;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 0.3rem;
    }
    .winner-banner {
        background: linear-gradient(135deg, #ECFDF5, #D1FAE5);
        border: 1px solid #A7F3D0;
        border-radius: 12px;
        padding: 1rem 1.5rem;
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }
    .winner-banner .trophy { font-size: 1.8rem; }
    .winner-banner .winner-text h3 {
        margin: 0;
        font-size: 1rem;
        font-weight: 700;
        color: #065F46;
    }
    .winner-banner .winner-text p {
        margin: 0.15rem 0 0 0;
        font-size: 0.85rem;
        color: #047857;
    }
    .step-header {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        margin-bottom: 0.75rem;
    }
    .step-number {
        background: linear-gradient(135deg, #5B6ABF, #7C3AED);
        color: white;
        width: 32px;
        height: 32px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 0.9rem;
        flex-shrink: 0;
    }
    .step-title {
        font-size: 1.2rem;
        font-weight: 700;
        color: #1A1A2E;
    }
    .data-card, .artifact-card {
        background: #FFFFFF;
        border: 1.5px solid #E5E7EB;
        border-radius: 14px;
        padding: 1.5rem;
        height: 100%;
        transition: border-color 0.2s, box-shadow 0.2s;
    }
    .data-card:hover, .artifact-card:hover {
        border-color: #5B6ABF;
        box-shadow: 0 4px 16px rgba(91,106,191,0.1);
    }
    .data-card h4, .artifact-card h4 {
        color: #1A1A2E;
        font-size: 1.05rem;
        font-weight: 700;
        margin-bottom: 0.4rem;
    }
    .data-card p, .artifact-card p {
        color: #6B7280;
        font-size: 0.9rem;
        line-height: 1.5;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #5B6ABF 0%, #7C3AED 100%);
        color: white !important;
        border: none;
        border-radius: 10px;
        padding: 0.7rem 1.5rem;
        font-size: 1rem;
        font-weight: 600;
        letter-spacing: -0.01em;
        transition: opacity 0.2s;
    }
    .stButton > button[kind="primary"]:hover {
        opacity: 0.9;
    }
    .stButton > button[kind="secondary"] {
        border-radius: 10px;
        border: 1.5px solid #D1D5DB;
        color: #374151;
        font-weight: 500;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.25rem;
        background: #F3F4F6;
        border-radius: 10px;
        padding: 0.25rem;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.85rem;
        color: #6B7280;
        padding: 0.5rem 1rem;
    }
    .stTabs [aria-selected="true"] {
        background: #FFFFFF !important;
        color: #1A1A2E !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    footer { visibility: hidden; }
    .stDeployButton { display: none; }
    .soft-divider {
        border: none;
        height: 1px;
        background: #E5E7EB;
        margin: 1.5rem 0;
    }
</style>
"""


def apply_page_style(st) -> None:
    """Apply page configuration and CSS."""
    st.set_page_config(**PAGE_CONFIG)
    st.markdown(APP_CSS, unsafe_allow_html=True)


def render_header(st) -> None:
    """Render the main page header."""
    st.markdown(
        """
        <div class="app-header">
            <h1>🔬 <span class="accent">RAG-OPS</span></h1>
            <p>
                Find the best chunking, embedding, and retrieval combo for your documents.
                Upload data, run benchmarks, reuse cached artifacts, and compare results.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<hr class="soft-divider">', unsafe_allow_html=True)

