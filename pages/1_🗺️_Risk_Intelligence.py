"""Page 1 — Risk Intelligence: live heatmap, hotspots, corridor leaderboard."""

import streamlit as st
import plotly.express as px
from streamlit_folium import st_folium

from app_core import inject_theme, get_engines, section, metric_card
from modules import visualizer as viz

st.set_page_config(page_title="Risk Intelligence — AegisTraffic", page_icon="🗺️", layout="wide")
inject_theme()

engines = get_engines()
intel = engines["intel"]

st.markdown('<div class="aegis-title">🗺️ Risk Intelligence</div>', unsafe_allow_html=True)
st.markdown('<div class="aegis-sub">Where Bengaluru chokes — and when.</div>', unsafe_allow_html=True)
st.write("")

incidents = intel.get_incidents_for_map()
junctions = intel.get_top_junctions(50)

# ── Controls ─────────────────────────────────────────────────────────────────
left, right = st.columns([3, 1])
with right:
    section("Live Risk Now")
    import datetime
    now = datetime.datetime.now()
    risk_now = intel.get_risk_right_now(hour=now.hour, day_of_week=now.weekday())
    color = "#fca5a5" if risk_now > 0.5 else "#fcd34d" if risk_now > 0.2 else "#86efac"
    st.markdown(metric_card(f"{risk_now*100:.0f}%", f"Risk · {now.strftime('%a %H:%M')}", color), unsafe_allow_html=True)
    st.write("")
    layer = st.radio("Map layer", ["Heatmap + Pins", "Heatmap only", "Junction pins only"], index=0)
    show_chronic = st.checkbox("Highlight chronic chokepoints", value=True)

with left:
    section("Bengaluru Incident Map")
    if layer == "Heatmap only":
        fmap = viz.incident_heatmap(incidents)
    elif layer == "Junction pins only":
        fmap = viz.junction_risk_map(junctions)
    else:
        fmap = viz.combined_risk_map(incidents, junctions)
    st_folium(fmap, height=520, width=None, returned_objects=[])

st.write("")

# ── Corridor leaderboard + cause donut ───────────────────────────────────────
c1, c2 = st.columns(2)
with c1:
    section("Top Risk Corridors")
    top = intel.get_top_corridors(10).copy()
    fig = px.bar(
        top.sort_values("corridor_risk_index"),
        x="corridor_risk_index", y="corridor", orientation="h",
        color="corridor_risk_index", color_continuous_scale="Turbo",
        labels={"corridor_risk_index": "Risk Index", "corridor": ""},
    )
    fig.update_layout(
        height=380, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e8edf6", coloraxis_showscale=False, margin=dict(l=0, r=10, t=10, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)

with c2:
    section("Incident Causes")
    from modules.data_pipeline import get_cause_distribution
    cd = get_cause_distribution(engines["df"]).head(8).reset_index()
    cd.columns = ["cause", "count"]
    fig2 = px.pie(cd, names="cause", values="count", hole=0.55,
                  color_discrete_sequence=px.colors.sequential.Plasma_r)
    fig2.update_layout(
        height=380, paper_bgcolor="rgba(0,0,0,0)", font_color="#e8edf6",
        margin=dict(l=0, r=0, t=10, b=0), legend=dict(font=dict(size=10)),
    )
    fig2.update_traces(textposition="inside", textinfo="percent")
    st.plotly_chart(fig2, use_container_width=True)

# ── Chronic chokepoints table ────────────────────────────────────────────────
if show_chronic:
    section("⚠️ Chronic Chokepoints (median clearance > 200 min)")
    chronic = intel.get_chronic_chokepoints().head(12)[
        ["junction", "incident_count", "median_closure_mins"]
    ].copy()
    chronic["median_closure_mins"] = chronic["median_closure_mins"].round(0).astype(int)
    chronic.columns = ["Junction", "Incidents", "Median Clearance (min)"]
    st.dataframe(chronic, use_container_width=True, hide_index=True)
