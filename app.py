"""
AegisTraffic — AI Traffic Command Copilot for Bengaluru
Home / Command Overview page. Run:  streamlit run app.py
"""

import streamlit as st
from app_core import inject_theme, get_engines, metric_card, section, sidebar_brand

st.set_page_config(
    page_title="AegisTraffic — Command Copilot",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_theme()
with st.sidebar:
    sidebar_brand()

engines = get_engines()
intel = engines["intel"]
stats = intel.get_summary_stats()

# ── Hero ────────────────────────────────────────────────────────────────────────
st.markdown('<div class="aegis-title">🛡️ AegisTraffic</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="aegis-sub"><span class="pulse"></span>'
    'AI Traffic Command Copilot · Bengaluru Traffic Police · '
    'Event-Driven Congestion Intelligence</div>',
    unsafe_allow_html=True,
)
st.write("")

# ── Live metric cards ────────────────────────────────────────────────────────────
section("Command Overview")
c1, c2, c3, c4 = st.columns(4)
c1.markdown(metric_card(f"{stats['total_incidents']:,}", "Incidents Analyzed", "#60a5fa", 0.0), unsafe_allow_html=True)
c2.markdown(metric_card(f"{stats['high_severity_pct']}%", "High Severity", "#fca5a5", 0.1), unsafe_allow_html=True)
c3.markdown(metric_card(f"{stats['planned_events']}", "Planned Events", "#a78bfa", 0.2), unsafe_allow_html=True)
c4.markdown(metric_card(f"{stats['chronic_junctions']}", "Chronic Chokepoints", "#fcd34d", 0.3), unsafe_allow_html=True)

st.write("")
c5, c6, c7, c8 = st.columns(4)
mi = engines["predictor"].get_model_info()
tri_acc = mi.get("triage_metrics", {}).get("accuracy", 0)
crit_recall = mi.get("binary_metrics", {}).get("recall", 0)
c5.markdown(metric_card(f"{tri_acc*100:.0f}%", "Triage Accuracy", "#5eead4", 0.0), unsafe_allow_html=True)
c6.markdown(metric_card(f"{crit_recall*100:.0f}%", "Critical-Event Recall", "#5eead4", 0.1), unsafe_allow_html=True)
c7.markdown(metric_card(f"{stats['corridors_monitored']}", "Corridors Monitored", "#93c5fd", 0.2), unsafe_allow_html=True)
c8.markdown(metric_card(f"{stats['median_closure_mins']:.0f}m", "Median Clearance", "#93c5fd", 0.3), unsafe_allow_html=True)

st.write("")
st.write("")

# ── What it does ─────────────────────────────────────────────────────────────────
section("What AegisTraffic Does")
cols = st.columns(3)
features = [
    ("🔮", "Forecast Impact", "Predicts severity & clearance time for any event before it escalates — with confidence and SHAP reasons."),
    ("🗺️", "Map the Risk", "Live heatmaps, chronic chokepoints, and corridor risk across all of Bengaluru."),
    ("📋", "Recommend Action", "Officers, barricades, tow, exact junctions & owning station — every number traceable."),
    ("🧭", "Plan Diversions", "Real OSRM reroutes around closures — zero licensing cost."),
    ("💬", "Ask in Plain Language", "Natural-language copilot (English & Kannada) grounded in real history."),
    ("📈", "Learn From History", "Logs every prediction vs actual, self-corrects per corridor over time."),
]
for i, (icon, title, desc) in enumerate(features):
    with cols[i % 3]:
        st.markdown(
            f"""<div class="metric-card" style="animation-delay:{i*0.08}s; min-height:150px">
                <div style="font-size:2rem">{icon}</div>
                <div style="font-weight:700; font-size:1.1rem; margin-top:6px">{title}</div>
                <div style="color:#9aa6bd; font-size:.9rem; margin-top:6px">{desc}</div>
            </div>""",
            unsafe_allow_html=True,
        )

st.write("")
st.info("👈 Use the sidebar to explore: **Risk Intelligence** · **Event Simulator** · **AI Copilot** · **Learning Loop**", icon="🧭")
