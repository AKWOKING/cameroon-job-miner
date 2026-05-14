"""
app.py
------
Cameroon Tech Job Market Miner — Streamlit Dashboard

Tabs:
  1. 📊 Skill Trends   — top N skills, filterable by portal / city / experience
  2. 🔗 Association Rules — skill co-occurrence patterns
  3. 🎯 Role Clusters  — K-Means archetype distribution
  4. 📋 Job Listings   — full searchable, filterable table with download

Run locally:
    streamlit run app.py

Deploy (Render / Streamlit Community Cloud):
    See render.yaml / README.md
"""

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config.settings import DB_PATH, DATA_DIR

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Cameroon Tech Job Market",
    page_icon="🇨🇲",
    layout="wide",
    initial_sidebar_state="expanded",
)

PORTAL_LABELS = {
    "emploi_cm":    "Emploi.cm",
    "talent_cm":    "Talent.cm",
    "expertini_cm": "Expertini.cm",
    "workconnect":  "WorkConnect",
}


# ── Data loading (cached) ──────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_data():
    if not DB_PATH.exists():
        return {}, {}, {}, {}
    conn = sqlite3.connect(DB_PATH)

    def safe_read(query, fallback=None):
        try:
            return pd.read_sql(query, conn)
        except Exception:
            return fallback if fallback is not None else pd.DataFrame()

    jobs        = safe_read("SELECT * FROM jobs_clean")
    freq        = safe_read("SELECT * FROM jobs_clean")  # we'll compute freq live
    rules       = safe_read("SELECT * FROM association_rules")
    clusters    = safe_read("SELECT * FROM job_clusters")
    profiles    = safe_read("SELECT * FROM job_clusters")

    conn.close()
    return jobs, rules, clusters, profiles


@st.cache_data(ttl=3600)
def compute_skill_freq(df: pd.DataFrame, source_filter, city_filter, exp_filter, top_n=30):
    """Compute skill frequencies with filters applied."""
    filtered = df.copy()
    if source_filter:
        filtered = filtered[filtered["source"].isin(source_filter)]
    if city_filter:
        filtered = filtered[filtered["city"].isin(city_filter)]
    if exp_filter:
        filtered = filtered[filtered["experience"].isin(exp_filter)]

    skill_counts = {}
    total = len(filtered)
    for skills_str in filtered["skills_extracted"].dropna():
        for skill in skills_str.split("|"):
            skill = skill.strip()
            if skill:
                skill_counts[skill] = skill_counts.get(skill, 0) + 1

    if not skill_counts:
        return pd.DataFrame(columns=["skill", "count", "pct"])

    rows = [
        {"skill": s, "count": c, "pct": round(100 * c / max(total, 1), 1)}
        for s, c in sorted(skill_counts.items(), key=lambda x: -x[1])
    ]
    return pd.DataFrame(rows).head(top_n)


# ── Sidebar ────────────────────────────────────────────────────────────────────
def build_sidebar(jobs_df: pd.DataFrame):
    st.sidebar.image(
        "https://upload.wikimedia.org/wikipedia/commons/4/4e/Flag_of_Cameroon.svg",
        width=80,
    )
    st.sidebar.title("🇨🇲 Cameroon Tech\nJob Market Miner")
    st.sidebar.markdown("---")

    all_sources = sorted(jobs_df["source"].dropna().unique()) if not jobs_df.empty else []
    all_cities  = sorted(jobs_df["city"].dropna().unique())   if not jobs_df.empty else []
    all_exp     = sorted(jobs_df["experience"].dropna().unique()) if not jobs_df.empty else []

    source_labels = [PORTAL_LABELS.get(s, s) for s in all_sources]
    src_map       = dict(zip(source_labels, all_sources))

    selected_labels = st.sidebar.multiselect(
        "🌐 Portal",
        options=source_labels,
        default=source_labels,
        help="Filter by job portal",
    )
    selected_sources = [src_map[l] for l in selected_labels]

    selected_cities = st.sidebar.multiselect(
        "📍 City",
        options=all_cities,
        default=all_cities,
        help="Filter by city",
    )

    selected_exp = st.sidebar.multiselect(
        "🎓 Experience Level",
        options=all_exp,
        default=all_exp,
        help="Filter by experience level",
    )

    top_n = st.sidebar.slider("Top N skills to display", min_value=5, max_value=50, value=20)

    st.sidebar.markdown("---")
    if not jobs_df.empty:
        st.sidebar.metric("Total Job Listings", len(jobs_df))
        avg_skills = jobs_df["skill_count"].mean() if "skill_count" in jobs_df.columns else 0
        st.sidebar.metric("Avg Skills / Listing", f"{avg_skills:.1f}")

    st.sidebar.markdown("---")
    st.sidebar.caption("Data refreshed weekly via GitHub Actions · Built with Streamlit + Plotly")

    return selected_sources, selected_cities, selected_exp, top_n


# ── Tab 1: Skill Trends ────────────────────────────────────────────────────────
def tab_skill_trends(jobs_df, sources, cities, exps, top_n):
    st.header("📊 In-Demand Tech Skills in Cameroon")

    if jobs_df.empty:
        st.warning("No data available yet. Run the scraper pipeline first.")
        _show_setup_instructions()
        return

    freq_df = compute_skill_freq(jobs_df, sources, cities, exps, top_n)

    if freq_df.empty:
        st.info("No skills found for the selected filters.")
        return

    col1, col2 = st.columns([3, 1])

    with col1:
        # Horizontal bar chart
        fig = px.bar(
            freq_df.sort_values("count"),
            x="count",
            y="skill",
            orientation="h",
            color="count",
            color_continuous_scale="Blues",
            labels={"count": "Job Listings", "skill": "Skill"},
            title=f"Top {len(freq_df)} Most Demanded Tech Skills",
            text="count",
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(
            coloraxis_showscale=False,
            height=max(400, len(freq_df) * 22),
            margin=dict(l=10, r=60, t=50, b=10),
            yaxis=dict(tickfont=dict(size=12)),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Ranking")
        display_df = freq_df[["skill", "count", "pct"]].rename(
            columns={"skill": "Skill", "count": "Jobs", "pct": "%"}
        )
        st.dataframe(display_df, use_container_width=True, hide_index=True, height=500)

    # ── Category breakdown ─────────────────────────────────────────────────────
    st.subheader("🗂️ Skills by Category")
    tax_path = DATA_DIR / "skill_taxonomy.csv"
    if tax_path.exists():
        tax = pd.read_csv(tax_path, dtype=str)[["canonical", "category"]]
        merged = freq_df.merge(tax, left_on="skill", right_on="canonical", how="left")
        merged["category"] = merged["category"].fillna("Other")
        cat_df = merged.groupby("category")["count"].sum().reset_index()
        cat_df = cat_df.sort_values("count", ascending=False)

        fig2 = px.pie(
            cat_df,
            names="category",
            values="count",
            title="Skill Demand by Category",
            color_discrete_sequence=px.colors.qualitative.Set3,
        )
        fig2.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig2, use_container_width=True)


# ── Tab 2: Association Rules ───────────────────────────────────────────────────
def tab_association_rules(rules_df):
    st.header("🔗 Skill Co-occurrence Patterns")
    st.markdown(
        "These rules show which skills are hired together. "
        "A **confidence of 0.70** means: *when a job requires A, it also requires B 70% of the time.*"
    )

    if rules_df.empty:
        st.warning("No association rules found yet. Run `python run_pipeline.py` first.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        min_conf  = st.slider("Min Confidence", 0.0, 1.0, 0.4, 0.05)
    with col2:
        min_lift  = st.slider("Min Lift", 1.0, 5.0, 1.2, 0.1)
    with col3:
        max_rules = st.slider("Max rules to show", 5, 50, 15)

    filtered = rules_df[
        (rules_df["confidence"] >= min_conf) &
        (rules_df["lift"]       >= min_lift)
    ].head(max_rules)

    if filtered.empty:
        st.info("No rules match the selected thresholds.")
        return

    # Bubble chart: x=support, y=confidence, size=lift
    fig = px.scatter(
        filtered,
        x="support",
        y="confidence",
        size="lift",
        color="lift",
        hover_name="if_skills",
        hover_data={"then_skills": True, "support": ":.3f", "confidence": ":.2f", "lift": ":.2f"},
        color_continuous_scale="Viridis",
        title="Association Rules — Support vs Confidence (bubble size = Lift)",
        labels={"support": "Support", "confidence": "Confidence"},
    )
    fig.update_layout(height=450)
    st.plotly_chart(fig, use_container_width=True)

    # Table
    st.subheader(f"Top {len(filtered)} Rules")
    display_rules = filtered.copy()
    display_rules.columns = ["If you need…", "You'll also need…", "Support", "Confidence", "Lift"]
    st.dataframe(display_rules, use_container_width=True, hide_index=True)

    # Download
    csv = filtered.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button("⬇ Download Rules CSV", csv, "association_rules.csv", "text/csv")


# ── Tab 3: Role Clusters ───────────────────────────────────────────────────────
def tab_clusters(jobs_df, clusters_df):
    st.header("🎯 Job Role Archetypes (K-Means Clustering)")
    st.markdown(
        "Jobs are grouped by their skill profiles. Each cluster represents "
        "a distinct role archetype in the Cameroonian tech market."
    )

    if clusters_df.empty or "archetype" not in clusters_df.columns:
        # Try to rebuild from jobs_df
        if not jobs_df.empty and "archetype" in jobs_df.columns:
            _render_clusters(jobs_df)
        else:
            st.warning("No cluster data yet. Run `python run_pipeline.py` to generate clusters.")
        return

    # Merge clusters with jobs for archetype column
    merged = jobs_df.merge(clusters_df[["raw_id", "archetype"]], on="raw_id", how="left") \
             if "archetype" not in jobs_df.columns else jobs_df

    _render_clusters(merged)


def _render_clusters(df):
    if "archetype" not in df.columns:
        st.warning("Archetype data not available.")
        return

    arch_counts = df["archetype"].value_counts().reset_index()
    arch_counts.columns = ["Archetype", "Count"]

    col1, col2 = st.columns([2, 1])

    with col1:
        fig = px.bar(
            arch_counts,
            x="Count",
            y="Archetype",
            orientation="h",
            color="Count",
            color_continuous_scale="Teal",
            title="Job Role Distribution",
            text="Count",
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(
            coloraxis_showscale=False,
            height=400,
            yaxis=dict(categoryorder="total ascending"),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Distribution")
        st.dataframe(arch_counts, use_container_width=True, hide_index=True)

    # Skill breakdown per archetype
    st.subheader("Skills by Archetype")
    selected_arch = st.selectbox("Select archetype to explore:", sorted(df["archetype"].dropna().unique()))
    arch_df = df[df["archetype"] == selected_arch]

    skill_counts = {}
    for skills_str in arch_df["skills_extracted"].dropna():
        for skill in skills_str.split("|"):
            skill = skill.strip()
            if skill:
                skill_counts[skill] = skill_counts.get(skill, 0) + 1

    if skill_counts:
        top_skills = pd.DataFrame(
            sorted(skill_counts.items(), key=lambda x: -x[1])[:15],
            columns=["Skill", "Count"],
        )
        fig2 = px.bar(
            top_skills.sort_values("Count"),
            x="Count", y="Skill", orientation="h",
            color="Count", color_continuous_scale="Oranges",
            title=f"Top Skills in '{selected_arch}' Cluster",
        )
        fig2.update_layout(coloraxis_showscale=False, height=380)
        st.plotly_chart(fig2, use_container_width=True)


# ── Tab 4: Job Listings ────────────────────────────────────────────────────────
def tab_listings(jobs_df, sources, cities, exps):
    st.header("📋 Job Listings")

    if jobs_df.empty:
        st.warning("No listings in the database yet.")
        return

    # Apply filters
    df = jobs_df.copy()
    if sources:
        df = df[df["source"].isin(sources)]
    if cities:
        df = df[df["city"].isin(cities)]
    if exps:
        df = df[df["experience"].isin(exps)]

    # Search box
    search = st.text_input("🔍 Search titles or companies", "")
    if search:
        mask = (
            df["title"].str.contains(search, case=False, na=False) |
            df["company"].str.contains(search, case=False, na=False)
        )
        df = df[mask]

    st.caption(f"Showing {len(df)} listings")

    # Display columns
    display_cols = ["title", "company", "city", "experience", "skills_extracted", "source", "date_posted", "url"]
    available = [c for c in display_cols if c in df.columns]
    show_df = df[available].copy()

    if "source" in show_df.columns:
        show_df["source"] = show_df["source"].map(PORTAL_LABELS).fillna(show_df["source"])
    if "skills_extracted" in show_df.columns:
        show_df["skills_extracted"] = show_df["skills_extracted"].str.replace("|", ", ", regex=False)

    show_df = show_df.rename(columns={
        "title": "Job Title",
        "company": "Company",
        "city": "City",
        "experience": "Experience",
        "skills_extracted": "Skills",
        "source": "Portal",
        "date_posted": "Posted",
        "url": "Link",
    })

    st.dataframe(show_df, use_container_width=True, hide_index=True, height=500)

    # Download
    csv = show_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button("⬇ Download Filtered Listings CSV", csv, "job_listings.csv", "text/csv")


# ── Setup instructions (shown when DB is empty) ────────────────────────────────
def _show_setup_instructions():
    st.info("""
**First-time setup:**

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the full pipeline (scrape → clean → mine)
python run_pipeline.py

# 3. Relaunch this dashboard
streamlit run app.py
```

Or run each stage separately:
```bash
python run_scrapers.py          # Phase 1: scrape all portals
python -m pipeline.cleaner      # Phase 2: clean + extract skills
python -m pipeline.miner        # Phase 3: Apriori + K-Means
```
    """)


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    jobs_df, rules_df, clusters_df, profiles_df = load_data()

    sources, cities, exps, top_n = build_sidebar(jobs_df)

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Skill Trends",
        "🔗 Association Rules",
        "🎯 Role Clusters",
        "📋 Job Listings",
    ])

    with tab1:
        tab_skill_trends(jobs_df, sources, cities, exps, top_n)

    with tab2:
        tab_association_rules(rules_df)

    with tab3:
        tab_clusters(jobs_df, clusters_df)

    with tab4:
        tab_listings(jobs_df, sources, cities, exps)


if __name__ == "__main__":
    main()
