"""Benchmark result rendering helpers for the Streamlit app."""

from __future__ import annotations


def render_saved_artifacts(st, run_artifacts) -> None:
    """Render saved artifact locations for the latest benchmark run."""
    if not run_artifacts:
        return

    st.markdown("")
    st.markdown(
        f"""
        <div class="artifact-card">
            <h4>Run artifacts saved</h4>
            <p><strong>Run ID:</strong> {run_artifacts.run_id}<br/>
            <strong>Directory:</strong> {run_artifacts.directory}<br/>
            <strong>CSV:</strong> {run_artifacts.results_csv}<br/>
            <strong>JSON:</strong> {run_artifacts.results_json}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_results(st, results_df, per_query_results, top_k, run_artifacts=None) -> None:
    """Render benchmark results, charts, and query details."""
    import pandas as pd
    import plotly.express as px
    import plotly.graph_objects as go

    st.markdown('<hr class="soft-divider">', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="step-header">
            <div class="step-number">3</div>
            <div class="step-title">Results</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    df = results_df
    if "error" in df.columns and df["error"].astype(str).str.len().gt(0).any():
        with st.expander("Configuration errors", expanded=False):
            st.dataframe(df[df["error"].astype(str).str.len() > 0], use_container_width=True)

    best_row = df.loc[df["recall@k"].idxmax()]
    st.markdown(
        f"""
        <div class="winner-banner">
            <div class="trophy">🏆</div>
            <div class="winner-text">
                <h3>Best: {best_row['chunker']} + {best_row['embedder']} + {best_row['retriever']}</h3>
                <p>
                    Recall@{top_k} {best_row['recall@k']:.3f}
                    &nbsp;&bull;&nbsp; Precision@{top_k} {best_row['precision@k']:.3f}
                    &nbsp;&bull;&nbsp; MRR {best_row['mrr']:.3f}
                    &nbsp;&bull;&nbsp; NDCG {best_row['ndcg@k']:.3f}
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_saved_artifacts(st, run_artifacts)
    st.markdown("")

    tab_leader, tab_heat, tab_charts, tab_details = st.tabs(
        ["Leaderboard", "Heatmaps", "Charts", "Per-Query Details"]
    )

    with tab_leader:
        display_df = df.copy().sort_values("recall@k", ascending=False).reset_index(drop=True)
        display_df.insert(0, "Rank", range(1, len(display_df) + 1))

        metric_cols = [
            column
            for column in display_df.columns
            if column
            not in ["Rank", "chunker", "embedder", "retriever", "num_chunks", "avg_chunk_size", "error"]
        ]
        styled = (
            display_df.style
            .format({column: "{:.3f}" for column in metric_cols if display_df[column].dtype != object})
            .background_gradient(subset=["recall@k"], cmap="Greens", vmin=0, vmax=1)
            .background_gradient(subset=["precision@k"], cmap="Greens", vmin=0, vmax=1)
            .background_gradient(subset=["mrr"], cmap="Blues", vmin=0, vmax=1)
            .background_gradient(subset=["ndcg@k"], cmap="Blues", vmin=0, vmax=1)
        )
        st.dataframe(styled, use_container_width=True, hide_index=True, height=420)

        col_csv, col_json, _ = st.columns([1, 1, 3])
        with col_csv:
            st.download_button(
                "Download CSV",
                display_df.to_csv(index=False),
                "rag_ops_results.csv",
                "text/csv",
                use_container_width=True,
            )
        with col_json:
            st.download_button(
                "Download JSON",
                display_df.to_json(orient="records", indent=2),
                "rag_ops_results.json",
                "application/json",
                use_container_width=True,
            )

    with tab_heat:
        metric_choice = st.selectbox(
            "Metric",
            ["recall@k", "precision@k", "mrr", "ndcg@k", "map@k", "hit_rate@k"],
            index=0,
        )
        retriever_types = df["retriever"].unique()
        for retriever_type in retriever_types:
            subset = df[df["retriever"] == retriever_type]
            if subset.empty:
                continue
            st.markdown(f"**{retriever_type} Retrieval**")
            pivot = subset.pivot_table(
                index="chunker",
                columns="embedder",
                values=metric_choice,
                aggfunc="first",
            )
            fig = px.imshow(
                pivot,
                text_auto=".3f",
                color_continuous_scale="Greens",
                aspect="auto",
                labels={"x": "Embedding Model", "y": "Chunking Strategy", "color": metric_choice},
            )
            fig.update_layout(
                height=max(280, len(pivot) * 90 + 60),
                margin=dict(l=10, r=10, t=30, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#1A1A2E"),
                coloraxis_colorbar=dict(thickness=15, len=0.8),
            )
            fig.update_xaxes(side="bottom")
            st.plotly_chart(
                fig,
                use_container_width=True,
                key=f"heatmap_{retriever_type}_{metric_choice}",
            )

    with tab_charts:
        chart_metric = st.selectbox(
            "Metric to chart",
            ["recall@k", "precision@k", "mrr", "ndcg@k", "map@k", "hit_rate@k"],
            index=0,
            key="chart_metric_select",
        )
        st.markdown(f"**All Configurations Ranked by {chart_metric}**")
        ranked = df.copy().sort_values(chart_metric, ascending=True)
        ranked["config"] = (
            ranked["chunker"] + " · " + ranked["embedder"] + " · " + ranked["retriever"]
        )
        fig_rank = px.bar(
            ranked,
            x=chart_metric,
            y="config",
            orientation="h",
            color=chart_metric,
            color_continuous_scale="Blues",
            range_color=[0, 1],
            labels={chart_metric: chart_metric, "config": ""},
            text=ranked[chart_metric].map("{:.3f}".format),
        )
        fig_rank.update_layout(
            height=max(300, len(ranked) * 44 + 60),
            margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#1A1A2E"),
            coloraxis_showscale=False,
            yaxis=dict(tickfont=dict(size=12)),
        )
        fig_rank.update_traces(textposition="outside")
        fig_rank.update_xaxes(range=[0, 1.1], gridcolor="#F3F4F6")
        st.plotly_chart(fig_rank, use_container_width=True, key="chart_ranked")

        st.markdown("**Multi-Metric Comparison**")
        metric_cols_all = ["recall@k", "precision@k", "mrr", "ndcg@k"]
        df_melt = df.copy()
        df_melt["config"] = (
            df_melt["chunker"] + " · " + df_melt["embedder"] + " · " + df_melt["retriever"]
        )
        df_melt = df_melt[["config"] + metric_cols_all].melt(
            id_vars="config",
            var_name="Metric",
            value_name="Score",
        )
        fig_multi = px.bar(
            df_melt,
            x="config",
            y="Score",
            color="Metric",
            barmode="group",
            color_discrete_sequence=["#5B6ABF", "#7C3AED", "#10B981", "#F59E0B"],
            labels={"config": "Configuration", "Score": "Score"},
        )
        fig_multi.update_layout(
            height=420,
            margin=dict(l=10, r=10, t=10, b=120),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#1A1A2E"),
            xaxis=dict(tickangle=-30, tickfont=dict(size=11)),
            yaxis=dict(gridcolor="#F3F4F6", range=[0, 1.05]),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        )
        st.plotly_chart(fig_multi, use_container_width=True, key="chart_multi_metric")

        st.markdown("**Best Configuration Profile**")
        radar_metrics = ["precision@k", "recall@k", "mrr", "ndcg@k", "map@k", "hit_rate@k"]
        available_metrics = [metric for metric in radar_metrics if metric in best_row.index]
        values = [best_row[metric] for metric in available_metrics]
        values.append(values[0])
        labels = available_metrics + [available_metrics[0]]
        fig_radar = go.Figure(
            data=go.Scatterpolar(
                r=values,
                theta=labels,
                fill="toself",
                fillcolor="rgba(91, 106, 191, 0.15)",
                line=dict(color="#5B6ABF", width=2.5),
                marker=dict(size=6, color="#5B6ABF"),
                name=f"{best_row['chunker']} · {best_row['embedder']} · {best_row['retriever']}",
            )
        )
        fig_radar.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 1], gridcolor="#E5E7EB", linecolor="#E5E7EB"),
                angularaxis=dict(gridcolor="#E5E7EB", linecolor="#E5E7EB"),
                bgcolor="rgba(0,0,0,0)",
            ),
            height=420,
            margin=dict(l=80, r=80, t=30, b=30),
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#1A1A2E"),
            showlegend=True,
            legend=dict(orientation="h", yanchor="top", y=-0.05, xanchor="center", x=0.5),
        )
        st.plotly_chart(fig_radar, use_container_width=True, key="chart_radar")

    with tab_details:
        if per_query_results:
            config_options = list(per_query_results.keys())
            selected_config = st.selectbox("Configuration", config_options)
            if selected_config:
                pq_df = pd.DataFrame(per_query_results[selected_config])
                show_misses = st.toggle("Show only misses", value=False)
                if show_misses and "hit" in pq_df.columns:
                    pq_df = pq_df[~pq_df["hit"]]
                st.dataframe(pq_df, use_container_width=True, hide_index=True)
        else:
            st.info("Run a benchmark to see per-query details.")

