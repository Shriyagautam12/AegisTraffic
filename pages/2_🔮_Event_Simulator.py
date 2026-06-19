"""Page 2 — Event Simulator (Gemini-first).
On Predict: runs our ML (grounded numbers) AND Gemini's structured operational
order, then renders rich cards — personnel by rank, special units, diversion
legs, and a phased timeline. Our ML shown as a compact 'grounded data' strip.
"""

import streamlit as st
import plotly.graph_objects as go
from streamlit_folium import st_folium

from app_core import inject_theme, get_engines, section, severity_badge, metric_card, sidebar_brand
from modules import visualizer as viz
from modules.data_pipeline import CORRIDOR_RISK_TIER, VEH_RISK_SCORE, norm_cat

st.set_page_config(page_title="Event Simulator — AegisTraffic", page_icon="🔮", layout="wide")
inject_theme()
with st.sidebar:
    sidebar_brand()

engines = get_engines()
predictor   = engines["predictor"]
retriever   = engines["retriever"]
recommender = engines["recommender"]
intel       = engines["intel"]
learning    = engines["learning"]
copilot     = engines["copilot"]

st.markdown('<div class="aegis-title">🔮 Event Impact Simulator</div>', unsafe_allow_html=True)
st.markdown('<div class="aegis-sub">Describe an event → get a full AI-drafted command plan, grounded in our models.</div>', unsafe_allow_html=True)
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
    cause    = a.selectbox("Event cause", CAUSES, index=2)
    corridor = b.selectbox("Corridor", CORRIDORS,
                           index=CORRIDORS.index("Airport New South Road") if "Airport New South Road" in CORRIDORS else 0)
    veh      = c.selectbox("Vehicle type (if any)", ["(none)"] + VEH, index=0)
    import datetime as _dt
    d, e, f, g = st.columns(4)
    start_date = d.date_input("Event date", value=_dt.date.today())
    start_time = e.time_input("Start time", value=_dt.time(18, 0), step=1800)
    duration   = f.slider("Duration (hrs)", 0.5, 12.0, 4.0, step=0.5)
    closure    = g.checkbox("Road closure", value=True)
    submitted = st.form_submit_button("⚡ Generate Command Plan", use_container_width=True)

if submitted:
    from modules.data_pipeline import PEAK_HOURS
    start_hr     = start_time.hour
    day_of_week  = start_date.weekday()   # 0=Mon … 6=Sun
    event = {
        "event_cause": cause, "corridor": corridor,
        "veh_type": None if veh == "(none)" else veh,
        "day_of_week": day_of_week, "hour": start_hr,
        "month": start_date.month,
        "duration_hrs": duration,
        "start_datetime_display": f"{start_date.strftime('%a %d %b %Y')} {start_time.strftime('%H:%M')}",
        "is_peak": 1 if start_hr in PEAK_HOURS else 0,
        "requires_road_closure": closure,
        "is_planned": 1 if cause in ["public_event","procession","vip_movement","protest","construction"] else 0,
        "priority": "High" if cause in ["vip_movement","public_event"] else "Low",
    }
    pred = predictor.predict(event)
    st.session_state["sim_event"] = event
    st.session_state["sim_pred"] = pred
    st.session_state.pop("sim_op", None)   # clear any prior AI narrative
    try:
        learning.log_prediction(event, pred)
    except Exception:
        pass

# ── Render ───────────────────────────────────────────────────────────────────
if "sim_pred" in st.session_state:
    event = st.session_state["sim_event"]
    pred = st.session_state["sim_pred"]

    # Resource numbers: ALWAYS from our deterministic rule engine (no Gemini)
    rplan = recommender.recommend(event, severity=pred["severity"])
    total_off = rplan["total_officers"]

    # Grounded ML strip (compact)
    section("Grounded Prediction (AegisTraffic ML)")
    g1, g2, g3, g4 = st.columns(4)
    with g1:
        st.markdown("Severity"); st.markdown(severity_badge(pred["severity"]), unsafe_allow_html=True)
        st.caption(f"{pred['confidence']*100:.0f}% confidence")
    g2.markdown(metric_card(f"{pred['duration_mins']:.0f}m", "Est. Clearance", "#60a5fa"), unsafe_allow_html=True)
    g3.markdown(metric_card("YES" if pred["is_critical"] else "no", "Critical?",
                "#fca5a5" if pred["is_critical"] else "#86efac"), unsafe_allow_html=True)
    g4.markdown(metric_card(rplan.get("owning_station", "—"), "Owning Station", "#a78bfa"), unsafe_allow_html=True)
    chips = "".join(f'<span class="chip">{r["feature"]} {("▲" if r["direction"]=="increases" else "▼")}</span>'
                    for r in pred["top_reasons"])
    st.markdown("**Why:** " + chips, unsafe_allow_html=True)

    st.write("")

    # ── Rank breakdown from total force (BTP proportions) ─────────────────────
    # Derive a rank breakdown from the total force (BTP proportions)
    def _ranks_from_total(n):
        dcp = 1 if n >= 80 else 0
        acp = max(0, round(n / 120)) if n >= 60 else 0
        pi  = max(1, round(n / 25)) if n >= 8 else (1 if n >= 4 else 0)
        psi = max(0, round(n / 12)) if n >= 12 else 0
        hg  = round(n * 0.20) if n >= 40 else 0          # home guards for large events
        constables = max(0, n - dcp - acp - pi - psi - hg)
        return dcp, acp, pi, psi, constables, hg
    dcp, acp, pi, psi, constables, hg = _ranks_from_total(total_off)

    section("👮 Personnel Deployment")
    ranks = [("DCP", dcp, "#fca5a5"), ("ACP", acp, "#fcd34d"),
             ("PI", pi, "#60a5fa"), ("PSI/ASI", psi, "#a78bfa"),
             ("Constables", constables, "#5eead4"), ("Home Guards", hg, "#93c5fd")]
    cols = st.columns(6)
    for col, (label, val, color) in zip(cols, ranks):
        col.markdown(metric_card(val, label, color), unsafe_allow_html=True)
    _start = event.get("hour", 0); _dur = rplan.get("duration_hrs", 1)
    _end = int((_start + _dur) % 24)
    _when = event.get("start_datetime_display", "")
    _window = f"{_start:02d}:00–{_end:02d}:00 ({_dur:g}h)"
    _shift = " · 🔁 spans multiple shifts — relief rotation factored in" if rplan.get("shift_rotation") else ""
    st.caption(f"Total force: **{total_off}** personnel "
               f"({rplan['officers']}/junction × {rplan['n_deploy_points']} deployment points) · "
               f"{_when} · {_window}{_shift}")
    st.caption(f"_{rplan['officer_breakdown']}_")

    # ── Logistics / special units (rule engine) ────────────────────────────────
    st.write("")
    section("🚧 Logistics & Special Units")
    units = [("Barricades", rplan["total_barricades"], "#fcd34d"),
             ("Tow Vehicles", rplan["tow_vehicles"], "#fca5a5"),
             ("Patrol Jeeps", rplan["patrol_jeeps"], "#60a5fa"),
             ("Command Vans", rplan["command_vans"], "#a78bfa")]
    cols = st.columns(4)
    for col, (label, val, color) in zip(cols, units):
        col.markdown(metric_card(val, label, color), unsafe_allow_html=True)
    st.caption(f"Tow class: **{rplan['tow_class']}**"
               + (f" · Equipment: {', '.join(rplan['special_equipment'])}" if rplan['special_equipment'] else ""))

    # ── AI narrative (diversion / timeline / command) — ON DEMAND via Gemini ──
    st.write("")
    section("🧭 Diversion & Operational Narrative")
    st.caption("Numbers above are AegisTraffic's deterministic engine. "
               "Click below to generate AI-drafted diversion routes, timeline & advisory.")
    if st.button("🧭 Show Diversion Routes & AI Plan", use_container_width=True):
        with st.spinner("Drafting diversion routes & timeline…"):
            st.session_state["sim_op"] = copilot.operational_plan(event, prediction=pred)

    op = st.session_state.get("sim_op", {})
    if op.get("available"):
        d = op["plan"]

        # ── Diversion legs ──────────────────────────────────────────────────────
        st.write("")
        colA, colB = st.columns(2)
        with colA:
            section("🧭 Diversion Routes")
            legs = d.get("diversion_legs", [])
            if legs:
                for leg in legs:
                    st.markdown(
                        f"""<div class="metric-card" style="padding:12px 14px">
                        <span style="color:#9aa6bd; font-size:.8rem">{leg.get('for_whom','Commuters')}</span><br>
                        <b>{leg.get('from','?')}</b> →
                        <span style="color:#60a5fa">{leg.get('via','?')}</span> →
                        <b>{leg.get('to','?')}</b></div>""", unsafe_allow_html=True)
            else:
                st.caption("No diversion required.")
            hgv = d.get("hgv_ban")
            if hgv and hgv.lower() != "not required":
                st.markdown(f"🚛 **HGV ban:** {hgv}")

        # ── Similar events ────────────────────────────────────────────────────────
        with colB:
            section("📜 What History Shows")
            summ = retriever.summarize_precedent(event, k=5)
            if summ["typical_closure_mins"] is not None:
                conf = " ⚠️ limited data" if summ["low_confidence"] else ""
                st.markdown(f"Typically clears in **~{summ['typical_closure_mins']:.0f} min**{conf} · "
                            f"{summ['high_severity_count']}/5 were High")
            for s in summ["similar_events"][:3]:
                cm = f"{s['closure_mins']:.0f} min" if s["closure_mins"] else "n/a"
                st.markdown(
                    f"""<div class="metric-card" style="padding:10px 13px">
                    <b>{s['date']}</b> · {s['day']} &nbsp;{severity_badge(s['severity'])}<br>
                    <span style="color:#9aa6bd; font-size:.85rem">{s['event_cause']} on {s['corridor']} · {cm}</span>
                    </div>""", unsafe_allow_html=True)

        # ── Phased timeline ──────────────────────────────────────────────────────
        st.write("")
        section("⏱️ Operational Timeline")
        tl = d.get("timeline", [])
        if tl:
            cols = st.columns(len(tl))
            for col, ph in zip(cols, tl):
                col.markdown(
                    f"""<div class="metric-card" style="min-height:170px; padding:14px">
                    <div style="font-weight:800; color:#60a5fa">{ph.get('phase','')}</div>
                    <div style="font-weight:700; margin-top:4px">{ph.get('label','')}</div>
                    <div style="color:#9aa6bd; font-size:.82rem; margin-top:8px">{ph.get('actions','')}</div>
                    </div>""", unsafe_allow_html=True)

        # ── Command & VMS ────────────────────────────────────────────────────────
        st.write("")
        cc1, cc2 = st.columns(2)
        with cc1:
            section("🎖️ Command & Control")
            st.markdown(d.get("command", "—"))
        with cc2:
            section("📢 Public Advisory (VMS)")
            st.markdown(f"""<div class="metric-card" style="border-color:#f59e0b; padding:14px">
                <span style="color:#fcd34d; font-family:monospace">{d.get('vms_advisory','—')}</span></div>""",
                unsafe_allow_html=True)

        st.caption("⚠️ Diversion routes & timeline are AI-drafted from operational norms — "
                   "verify against current ground conditions.")

    elif op and not op.get("available"):
        # Button was clicked but Gemini failed — numbers above are unaffected
        st.warning(f"AI narrative unavailable ({op.get('reason','no LLM')}). "
                   f"Resource numbers above are from the deterministic engine and remain valid.",
                   icon="⚠️")

    # ── Severity probabilities ────────────────────────────────────────────────
    st.write("")
    section("Severity Probabilities")
    probs = pred["probabilities"]
    fig = go.Figure(go.Bar(
        x=[probs["Low"], probs["Medium"], probs["High"]], y=["Low", "Medium", "High"], orientation="h",
        marker_color=["#22c55e", "#f59e0b", "#ef4444"],
        text=[f"{probs['Low']*100:.0f}%", f"{probs['Medium']*100:.0f}%", f"{probs['High']*100:.0f}%"],
        textposition="auto"))
    fig.update_layout(height=180, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font_color="#e8edf6", margin=dict(l=0, r=0, t=4, b=0),
                      xaxis=dict(range=[0,1], showticklabels=False))
    st.plotly_chart(fig, use_container_width=True)

    # ── Optional live OSRM diversion map ──────────────────────────────────────
    if event.get("requires_road_closure"):
        section("🗺️ Live Diversion Route (OSRM)")
        if st.button("Compute live reroute on map"):
            with st.spinner("Routing via OpenStreetMap…"):
                centroid = recommender._corridor_centroids.get(norm_cat(event["corridor"]))
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
                        st.warning("OSRM unreachable right now.")
                else:
                    st.info("No centroid on record for this corridor.")
