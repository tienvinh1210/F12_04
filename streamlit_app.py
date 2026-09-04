"""
Livestock Dashboard — Streamlit entry point
Run locally:  streamlit run streamlit_app.py
Deploy:       Streamlit Community Cloud → this file as Main file path
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

BACKEND = Path(__file__).resolve().parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.auth.passwords import verify_password
from app.constants import MEASURE_LABELS, MEASURE_UNITS, MONTH_NAMES
from app.db import fetch_one, get_user_farms
from app.models.schemas import FilterState
from app.services.chart_service import CohortService, DistributionService, TimeseriesService
from app.services.data_service import DataService
from app.services.filter_service import FilterService
from app.services.summary_service import SummaryService
from app.utils.anonymize import anonymize_records

st.set_page_config(
    page_title="Livestock Dashboard",
    page_icon="🐄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Brand colours (match design system)
st.markdown(
    """
    <style>
      .stApp { background-color: #f4f5f6; }
      [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e9ecef; }
      h1, h2, h3 { color: #1B4332 !important; }
      div[data-testid="stMetricValue"] { color: #1B4332; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _configure_db_from_secrets() -> None:
    """Prefer Streamlit secrets for DATABASE_URL when present."""
    try:
        if "DATABASE_URL" in st.secrets:
            import os

            os.environ["DATABASE_URL"] = st.secrets["DATABASE_URL"]
            from app.config import get_settings

            get_settings.cache_clear()
            # Reset DB pool so new URL is used
            import app.db as db

            if db._pool is not None:
                try:
                    db._pool.closeall()
                except Exception:
                    pass
                db._pool = None
    except Exception:
        pass


def login_user(username: str, password: str) -> dict | None:
    user = fetch_one(
        "SELECT id, username, password_hash, is_admin, is_active FROM users WHERE username = %s",
        (username,),
    )
    if not user or not user["is_active"]:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    farms = get_user_farms(user["id"])
    return {
        "id": user["id"],
        "username": user["username"],
        "is_admin": user["is_admin"],
        "farms": farms,
    }


def render_login() -> None:
    st.markdown("## Welcome to Livestock Dashboard")
    st.caption("Advanced Analytics for Livestock Management")
    with st.form("login_form"):
        username = st.text_input("Username", value="")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In", type="primary", use_container_width=True)
        if submitted:
            try:
                user = login_user(username.strip(), password)
            except Exception as exc:
                st.error(f"Cannot connect to database: {exc}")
                return
            if user:
                st.session_state["user"] = user
                st.session_state["farm_id"] = user["farms"][0]["farm_id"] if user["farms"] else "KF"
                st.rerun()
            else:
                st.error("Invalid credentials")


@st.cache_data(ttl=120, show_spinner="Loading farm data…")
def load_farm_df(farm_id: str):
    return FilterService.load_farm_dataframe(farm_id)


def build_filters_from_sidebar(choices: dict, is_admin: bool) -> FilterState:
    farm_id = st.session_state.get("farm_id", "KF")
    years = choices.get("years") or [2023]
    default_year = choices.get("max_year") or years[0]

    st.sidebar.markdown("### Data Filters")
    year = st.sidebar.selectbox("Year", years, index=years.index(default_year) if default_year in years else 0)
    month = st.sidebar.selectbox("Month", choices.get("months") or MONTH_NAMES, index=0)
    day = st.sidebar.selectbox("Day", choices.get("days") or ["All"], index=0)

    sex = st.sidebar.multiselect("Sex", choices.get("sexes") or ["Overall"], default=["Overall"])
    treatment = st.sidebar.multiselect(
        "Treatment", choices.get("treatments") or ["Overall"], default=["Overall"]
    )
    breed = st.sidebar.multiselect("Breed", choices.get("breeds") or ["Overall"], default=["Overall"])
    mob = st.sidebar.multiselect("Mob", choices.get("mobs") or ["Overall"], default=["Overall"])

    eid = ["Overall"]
    if is_admin and choices.get("eids"):
        eid = st.sidebar.multiselect("EID", choices["eids"], default=["Overall"])

    measure_opts = choices.get("measures") or [{"key": "finalpweight", "label": MEASURE_LABELS["finalpweight"]}]
    measure_labels = {m["label"]: m["key"] for m in measure_opts}
    measure_label = st.sidebar.selectbox("Measure", list(measure_labels.keys()), index=0)
    measure = measure_labels[measure_label]

    # Empty multi-select → Overall
    sex = sex or ["Overall"]
    treatment = treatment or ["Overall"]
    breed = breed or ["Overall"]
    mob = mob or ["Overall"]
    eid = eid or ["Overall"]

    return FilterState(
        farm_id=farm_id,
        year=int(year),
        month=month,
        day=day if day == "All" else int(day),
        sex=sex,
        treatment=treatment,
        breed=breed,
        mob=mob,
        eid=eid,
        measure=measure,
    )


def format_kpi(val: float, measure: str) -> str:
    unit = MEASURE_UNITS.get(measure, "")
    if measure == "animalvalue":
        return f"${val:,.2f}"
    return f"{val:.2f} {unit}".strip()


def page_summary(filters: FilterState, grouped, is_admin: bool) -> None:
    st.subheader("Summary Stats")
    st.info("Statistics for each animal group based on your current filter selections.")
    if grouped.empty:
        st.warning("No data matches the current filters.")
        return
    groups = SummaryService.compute_stats(grouped, filters.measure)
    for g in groups:
        st.markdown(f"##### {g['full_group']}")
        cols = st.columns(4)
        for col, key in zip(cols, ["last_day", "last_15_days", "last_month", "overall"]):
            w = g["windows"][key]
            with col:
                st.metric(w["label"], format_kpi(w["mean"], filters.measure))
                st.caption(
                    f"Min {format_kpi(w['min'], filters.measure)} · "
                    f"Max {format_kpi(w['max'], filters.measure)} · "
                    f"Median {format_kpi(w['median'], filters.measure)} · n={w['count']}"
                )


def page_timeseries(filters: FilterState, grouped, note: str | None) -> None:
    st.subheader("Time Series")
    st.info("Tip: click legend items to toggle series visibility.")
    if note:
        st.caption(note)
    if grouped.empty:
        st.warning("No data matches the current filters.")
        return
    show_smooth = st.checkbox("Show trend line", value=False)
    data = TimeseriesService.compute(grouped, filters.measure, show_smooth)
    import plotly.graph_objects as go

    fig = go.Figure()
    groups = sorted({s["group"] for s in data["series"]})
    for g in groups:
        pts = sorted([s for s in data["series"] if s["group"] == g], key=lambda x: x["date"])
        is_trend = "(trend)" in g
        fig.add_trace(
            go.Scatter(
                x=[p["date"] for p in pts],
                y=[p["value"] for p in pts],
                mode="lines" if is_trend else "lines+markers",
                name=g,
                line=dict(dash="dash" if is_trend else "solid"),
                marker=dict(size=5),
                customdata=[p["count"] for p in pts],
                hovertemplate="%{fullData.name}<br>%{x}<br>Avg: %{y:.2f}<br>n=%{customdata}<extra></extra>",
            )
        )
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title=data["y_label"],
        legend_title="Animal Group",
        height=520,
        margin=dict(t=20),
        hovermode="closest",
    )
    st.plotly_chart(fig, use_container_width=True)

    cov = FilterService.combo_coverage(
        DataService.get_filtered_data(filters, st.session_state["user"]["is_admin"])[0],
        filters,
        st.session_state["user"]["is_admin"],
    )
    if cov["expected"] > 1 and cov["missing"] > 0:
        with st.expander(f"Showing {cov['present']} of {cov['expected']} combinations ({cov['missing']} empty)"):
            for g in cov["missing_groups"][:20]:
                st.write(f"• {g}")


def page_distributions(filters: FilterState, grouped) -> None:
    st.subheader("Distributions")
    if grouped.empty:
        st.warning("No data matches the current filters.")
        return
    bins = st.slider("Histogram bins", 10, 50, 20, 5)
    data = DistributionService.compute(grouped, filters.measure, bins)
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(rows=1, cols=2, subplot_titles=("Histogram", "Box plot"))
    for g in data["histogram"]["groups"]:
        fig.add_trace(go.Histogram(x=g["values"], name=g["group"], opacity=0.55, nbinsx=bins), row=1, col=1)
    fig.add_vline(x=data["histogram"]["mean"], line_dash="dash", line_color="#B08968", row=1, col=1)
    fig.add_vline(x=data["histogram"]["median"], line_dash="dot", line_color="#7B241C", row=1, col=1)
    for g in data["boxplot"]["groups"]:
        fig.add_trace(
            go.Box(y=[g["min"], g["q1"], g["median"], g["q3"], g["max"]], name=g["group"], boxpoints=False),
            row=1,
            col=2,
        )
    fig.update_layout(barmode="overlay", height=480, margin=dict(t=40), showlegend=True)
    st.plotly_chart(fig, use_container_width=True)


def page_cohorts(filters: FilterState, filtered, grouped) -> None:
    st.subheader("Cohorts")
    pct = st.selectbox("Top/Bottom percentile", [10, 15, 20], index=0)
    result = CohortService.analyze(filtered, grouped, filters.measure, pct, filters)
    if result["show_mixed_warning"]:
        st.warning("You selected both Overall and specific values — rankings use the filtered set.")
    if result["total_animals"] == 0:
        st.warning("No animals in selection.")
        return
    c1, c2 = st.columns(2)
    is_admin = st.session_state["user"]["is_admin"]
    with c1:
        st.markdown("#### Top cohort")
        st.metric("Average", format_kpi(result["top"]["average"], filters.measure))
        st.caption(f"Min {result['top']['min']} · Max {result['top']['max']} · n={result['top']['count']}")
        top = anonymize_records(result["top"]["animals"], is_admin)
        st.dataframe(top, use_container_width=True, hide_index=True)
    with c2:
        st.markdown("#### Bottom cohort")
        st.metric("Average", format_kpi(result["bottom"]["average"], filters.measure))
        st.caption(f"Min {result['bottom']['min']} · Max {result['bottom']['max']} · n={result['bottom']['count']}")
        bottom = anonymize_records(result["bottom"]["animals"], is_admin)
        st.dataframe(bottom, use_container_width=True, hide_index=True)

    import plotly.express as px

    if result["timeline"]:
        tdf = __import__("pandas").DataFrame(result["timeline"])
        fig = px.line(tdf, x="date", y="value", color="cohort", title="Cohort timeline")
        fig.update_layout(height=400, margin=dict(t=40))
        st.plotly_chart(fig, use_container_width=True)


def page_data(filters: FilterState, filtered, is_admin: bool) -> None:
    st.subheader("Data Management")
    if filtered.empty:
        st.warning("No data matches the current filters.")
        return
    records = FilterService.df_to_records(filtered)
    records = anonymize_records(records, is_admin)
    import pandas as pd

    table = pd.DataFrame(records)
    cols = [c for c in ["date", "eid", "sex", "breed", "treatment", "mob", filters.measure] if c in table.columns]
    st.dataframe(table[cols] if cols else table, use_container_width=True, height=480)
    csv = table.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", csv, file_name=f"{filters.farm_id}_export.csv", mime="text/csv")


def page_customise(filters: FilterState, filtered) -> None:
    st.subheader("Customise chart")
    st.caption("Build a quick chart from the filtered dataset.")
    if filtered.empty:
        st.warning("No data matches the current filters.")
        return
    import plotly.express as px

    chart_type = st.selectbox("Type", ["line", "bar", "scatter", "box", "histogram"])
    x_col = st.selectbox("X", ["date", "sex", "breed", "mob", "treatment"])
    y_col = st.selectbox("Y", list(MEASURE_LABELS.keys()), index=0)
    group_col = st.selectbox("Group", ["None", "sex", "breed", "mob", "treatment"])
    df = filtered.copy()
    if "treatment" in df.columns:
        df["treatment"] = df["treatment"].fillna("No Treatment")
    if chart_type == "histogram":
        fig = px.histogram(df, x=y_col, color=None if group_col == "None" else group_col, nbins=20)
    elif chart_type == "box":
        fig = px.box(df, x=None if group_col == "None" else group_col, y=y_col)
    else:
        gcols = [x_col] + ([] if group_col == "None" else [group_col])
        agg = df.groupby(gcols)[y_col].mean().reset_index()
        kwargs = dict(x=x_col, y=y_col, color=None if group_col == "None" else group_col)
        fig = {"line": px.line, "bar": px.bar, "scatter": px.scatter}[chart_type](agg, **kwargs)
    fig.update_layout(height=480, margin=dict(t=20))
    st.plotly_chart(fig, use_container_width=True)


def render_dashboard() -> None:
    user = st.session_state["user"]
    farm_id = st.session_state.get("farm_id", "KF")

    with st.sidebar:
        st.markdown(f"**{user['username']}** · {'Admin' if user['is_admin'] else 'User'}")
        farm_names = {f["farm_id"]: f["farm_name"] for f in user["farms"]} or {"KF": "Killara Feedlot"}
        farm_id = st.selectbox(
            "Farm",
            list(farm_names.keys()),
            format_func=lambda x: f"{farm_names.get(x, x)} ({x})",
            index=list(farm_names.keys()).index(farm_id) if farm_id in farm_names else 0,
        )
        st.session_state["farm_id"] = farm_id
        if st.button("Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    try:
        choices = FilterService.get_filter_choices(farm_id, user["is_admin"])
    except Exception as exc:
        st.error(f"Database error: {exc}")
        return

    filters = build_filters_from_sidebar(choices, user["is_admin"])
    filters.farm_id = farm_id

    try:
        filtered, grouped, _, total = DataService.get_filtered_data(filters, user["is_admin"])
    except Exception as exc:
        st.error(f"Query failed: {exc}")
        return

    st.sidebar.caption(f"Showing **{len(filtered):,}** of **{total:,}** records")
    note = DataService.get_common_note(filters, grouped)

    st.title("Livestock Dashboard")
    st.caption(farm_names.get(farm_id, farm_id))

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        ["Summary", "Time Series", "Distributions", "Cohorts", "Data", "Customise"]
    )
    with tab1:
        page_summary(filters, grouped, user["is_admin"])
    with tab2:
        page_timeseries(filters, grouped, note)
    with tab3:
        page_distributions(filters, grouped)
    with tab4:
        page_cohorts(filters, filtered, grouped)
    with tab5:
        page_data(filters, filtered, user["is_admin"])
    with tab6:
        page_customise(filters, filtered)


def main() -> None:
    _configure_db_from_secrets()
    if "user" not in st.session_state:
        col1, col2, col3 = st.columns([1, 1.2, 1])
        with col2:
            render_login()
        return
    render_dashboard()


main()
