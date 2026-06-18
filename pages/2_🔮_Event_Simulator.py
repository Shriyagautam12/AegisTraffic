"""Page 2 — Event Simulator: predict severity/duration, explain, find precedents,
recommend resources, and optionally compute an OSRM diversion."""

import streamlit as st
import plotly.graph_objects as go
from streamlit_folium import st_folium

from app_core import inject_theme, get_engines, section, severity_badge, metric_card
from modules import visualizer as viz
from modules.data_pipeline import CORRIDOR_RISK_TIER, CAUSE_SEVERITY_SCORE, VEH_RISK_SCORE

st.set_page_config(page_title="Event Simulator — AegisTraffic", page_icon="🔮", layout="wide")
inject_theme()

engines = get_engines()
predictor   = engines["predictor"]
retriever   = engines["retriever"]
recommender = engines["recommender"]
intel       = engines["intel"]
learning    = engines["learning"]

st.markdown('<div class="aegis-title">🔮 Event Impact Simulator</div>', unsafe_allow_html=True)
st.markdown('<div class="aegis-sub">Type in an event — get severity, precedent, resources, and a diversion plan.</div>', unsafe_allow_html=True)
st.write("")

CAUSES = ["public_event", "procession", "vip_movement", "protest", "construction",
          "accident", "vehicle_breakdown", "tree_fall", "water_logging", "pot_holes", "congestion"]
CORRIDORS = sorted([c for c in CORRIDOR_RISK_TIER.keys()])
VEH = sorted(VEH_RISK_SCORE.keys())
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# ── Input form ───────────────────────────────────────────────────────────────
with st.form("sim"):
    section("Describe the Event")
    a, b, c = st.columns(3)
    cause    = a.selectbox("Event cause", CAUSES, index=0)
    corridor = b.selectbox("Corridor", CORRIDORS, index=CORRIDORS.index("CBD 2") if "CBD 2" in CORRIDORS else 0)
    veh      = c.selectbox("Vehicle type (if any)", ["(none)"] + VEH, index=0)
    d, e, f = st.columns(3)
    day      = d.selectbox("Day", DAYS, index=4)
    hour     = e.slider("Hour of day", 0, 23, 19)
    closure  = f.checkbox("Requires road closure", value=True)
    submitted = st.form_submit_button("⚡ Predict Impact", use_container_width=True)

if submitted:
    event = {
        "event_cause": cause, "corridor": corridor,
        "veh_type": None if veh == "(none)" else veh,
        "day_of_week": DAYS.index(day), "hour": hour,
        "requires_road_closure": closure,
        "is_planned": 1 if cause in ["public_event","procession","vip_movement","protest","construction"] else 0,
        "priority": "High" if cause in ["vip_movement","public_event"] else "Low",
    }
    pred = predictor.predict(event)
    st.session_state["sim_event"] = event
    st.session_state["sim_pred"] = pred

    # log to learning loop
    try:
        learning.log_prediction(event, pred)
    except Exception:
        pass

if "sim_pred" in st.session_state:
    event = st.session_state["sim_event"]
    pred = st.session_state["sim_pred"]

    # ── Prediction headline ──────────────────────────────────────────────────
    st.write("")
    section("Prediction")
    p1, p2, p3 = st.columns([1.2, 1, 1])
    with p1:
        st.markdown("Severity")
        st.markdown(severity_badge(pred["severity"]), unsafe_allow_html=True)
        st.caption(f"{pred['confidence']*100:.0f}% confidence")
    p2.markdown(metric_card(f"{pred['duration_mins']:.0f}m", "Est. Clearance", "#60a5fa"), unsafe_allow_html=True)
    crit = "YES" if pred["is_critical"] else "no"
    p3.markdown(metric_card(crit, "Critical Event?", "#fca5a5" if pred["is_critical"] else "#86efac"), unsafe_allow_html=True)

    rng = pred["duration_range"]
    st.caption(f"Likely clearance window: {rng[0]:.0f}–{rng[1]:.0f} min")

    # SHAP reasons
    st.markdown("**Why this prediction?**")
    chips = "".join(
        f'<span class="chip">{r["feature"]} {("▲" if r["direction"]=="increases" else "▼")}</span>'
        for r in pred["top_reasons"]
    )
    st.markdown(chips, unsafe_allow_html=True)

    st.write("")
    colL, colR = st.columns(2)

    # ── Similar events ────────────────────────────────────────────────────────
    with colL:
        section("📜 What History Shows")
        summ = retriever.summarize_precedent(event, k=5)
        if summ["typical_closure_mins"] is not None:
            conf = " ⚠️ limited data" if summ["low_confidence"] else ""
            st.markdown(f"Typically clears in **~{summ['typical_closure_mins']:.0f} min**{conf} "
                        f"· {summ['high_severity_count']}/5 were High severity")
        for s in summ["similar_events"][:3]:
            cm = f"{s['closure_mins']:.0f} min" if s["closure_mins"] else "n/a"
            st.markdown(
                f"""<div class="metric-card" style="padding:12px 14px">
                <b>{s['date']}</b> · {s['day']} &nbsp; {severity_badge(s['severity'])}<br>
                <span style="color:#9aa6bd">{s['event_cause']} on {s['corridor']} · clearance {cm}</span>
                </div>""", unsafe_allow_html=True)

    # ── Resource recommendation ───────────────────────────────────────────────
    with colR:
        section("📋 Deployment Plan")
        plan = recommender.recommend(event, severity=pred["severity"])
        r1, r2, r3 = st.columns(3)
        r1.markdown(metric_card(plan["officers"], "Officers", "#60a5fa"), unsafe_allow_html=True)
        r2.markdown(metric_card(plan["barricades"], "Barricades", "#a78bfa"), unsafe_allow_html=True)
        r3.markdown(metric_card(plan["tow_vehicles"], "Tow", "#fcd34d"), unsafe_allow_html=True)
        st.markdown(f"**Deploy at:** {', '.join(plan['deploy_at'])}")
        st.markdown(f"**Station:** {plan['owning_station']}")
        if plan["special_equipment"]:
            st.markdown(f"**Equipment:** {', '.join(plan['special_equipment'])}")
        st.caption(f"Officer math: {plan['officer_breakdown']}")

    # ── Probability gauge ─────────────────────────────────────────────────────
    st.write("")
    section("Severity Probabilities")
    probs = pred["probabilities"]
    fig = go.Figure(go.Bar(
        x=[probs["Low"], probs["Medium"], probs["High"]],
        y=["Low", "Medium", "High"], orientation="h",
        marker_color=["#22c55e", "#f59e0b", "#ef4444"],
        text=[f"{probs['Low']*100:.0f}%", f"{probs['Medium']*100:.0f}%", f"{probs['High']*100:.0f}%"],
        textposition="auto",
    ))
    fig.update_layout(height=200, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font_color="#e8edf6", margin=dict(l=0, r=0, t=4, b=0), xaxis=dict(range=[0,1], showticklabels=False))
    st.plotly_chart(fig, use_container_width=True)

    # ── Optional diversion ────────────────────────────────────────────────────
    if event.get("requires_road_closure"):
        section("🧭 Diversion Plan (live OSRM)")
        st.caption("Computes a real reroute around the closure. Click to fetch (uses live routing).")
        if st.button("Compute diversion route"):
            with st.spinner("Routing via OpenStreetMap…"):
                centroid = recommender._corridor_centroids.get(
                    __import__("modules.data_pipeline", fromlist=["norm_cat"]).norm_cat(event["corridor"]))
                if centroid:
                    origin = (centroid[0] - 0.01, centroid[1] - 0.01)
                    dest   = (centroid[0] + 0.01, centroid[1] + 0.01)
                    ev = dict(event); ev["latitude"], ev["longitude"] = centroid
                    dplan = recommender.diversion_plan(ev, origin, dest)
                    if dplan.get("available") and dplan.get("diverted_route"):
                        dc1, dc2 = st.columns(2)
                        dc1.markdown(metric_card(f"{dplan['normal_route']['duration_mins']:.0f}m", "Direct (blocked)", "#fca5a5"), unsafe_allow_html=True)
                        dc2.markdown(metric_card(f"{dplan['diverted_route']['duration_mins']:.0f}m", f"Via {dplan['alternate_corridor']}", "#86efac"), unsafe_allow_html=True)
                        st.caption(f"Time penalty: +{dplan['time_penalty_mins']:.0f} min")
                        st_folium(viz.diversion_map(origin, dest, dplan), height=380, returned_objects=[])
                    else:
                        st.warning("Diversion routing unavailable right now (OSRM unreachable).")
                else:
                    st.info("No centroid on record for this corridor.")
