"""Page 4 — Learning Loop: prediction-vs-actual accuracy + learned corrections."""

import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go

from app_core import inject_theme, get_engines, section, metric_card, sidebar_brand
from utils.constants import LEARNING_DB_PATH

st.set_page_config(page_title="Learning Loop — AegisTraffic", page_icon="📈", layout="wide")
inject_theme()
with st.sidebar:
    sidebar_brand()

engines = get_engines()
learning = engines["learning"]

st.markdown('<div class="aegis-title">📈 Post-Event Learning Loop</div>', unsafe_allow_html=True)
st.markdown('<div class="aegis-sub">Every prediction is logged, compared to reality, and used to self-correct.</div>', unsafe_allow_html=True)
st.write("")

report = learning.get_accuracy_report()

# ── Headline metrics ─────────────────────────────────────────────────────────
section("System Performance")
m1, m2, m3, m4 = st.columns(4)
m1.markdown(metric_card(f"{report['total_predictions']}", "Predictions Logged", "#60a5fa"), unsafe_allow_html=True)
m2.markdown(metric_card(f"{report['total_outcomes']}", "Outcomes Recorded", "#a78bfa"), unsafe_allow_html=True)
sev_acc = f"{report['severity_accuracy']*100:.0f}%" if report["severity_accuracy"] is not None else "—"
m3.markdown(metric_card(sev_acc, "Severity Accuracy", "#5eead4"), unsafe_allow_html=True)
mde = f"{report['median_duration_error_mins']:.0f}m" if report["median_duration_error_mins"] is not None else "—"
m4.markdown(metric_card(mde, "Median Duration Error", "#fcd34d"), unsafe_allow_html=True)

st.write("")

# ── Learned corrections ──────────────────────────────────────────────────────
c1, c2 = st.columns(2)
with c1:
    section("🧠 Learned Corridor Corrections")
    corr = learning.get_corridor_corrections()
    if corr:
        st.caption("Where the model has learned to adjust its duration estimates from observed reality.")
        for item in corr[:10]:
            direction = "▲ longer" if item["correction_factor"] > 1 else "▼ shorter"
            st.markdown(
                f"""<div class="metric-card" style="padding:12px 14px">
                <b>{item['corridor'].title()}</b> &nbsp;→&nbsp;
                <span style="color:#60a5fa">×{item['correction_factor']}</span>
                <span style="color:#9aa6bd"> ({direction} than predicted)</span>
                </div>""", unsafe_allow_html=True)
    else:
        st.info("No corrections learned yet — needs ≥5 closed outcomes per corridor. "
                "Use the Simulator/Copilot and record outcomes to see the system learn.", icon="🧠")

with c2:
    section("Predicted vs Actual")
    try:
        con = sqlite3.connect(str(LEARNING_DB_PATH))
        df = pd.read_sql(
            """SELECT p.pred_duration, o.actual_duration, p.corridor
               FROM outcomes o JOIN predictions p ON o.prediction_id=p.prediction_id
               WHERE p.pred_duration>0 AND o.actual_duration>0""", con)
        con.close()
    except Exception:
        df = pd.DataFrame()

    if len(df):
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["pred_duration"], y=df["actual_duration"], mode="markers",
            marker=dict(size=11, color="#60a5fa", line=dict(width=1, color="#bfdbfe")),
            text=df["corridor"], hovertemplate="%{text}<br>pred %{x:.0f} → actual %{y:.0f} min<extra></extra>"))
        lim = max(df["pred_duration"].max(), df["actual_duration"].max()) * 1.1
        fig.add_trace(go.Scatter(x=[0, lim], y=[0, lim], mode="lines",
                                 line=dict(dash="dash", color="#64748b"), name="perfect"))
        fig.update_layout(height=340, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          font_color="#e8edf6", showlegend=False,
                          xaxis_title="Predicted (min)", yaxis_title="Actual (min)",
                          margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No outcome data yet. Record some outcomes below to populate this chart.", icon="📊")

st.write("")

# ── Demo: record an outcome ──────────────────────────────────────────────────
section("🔁 Record an Outcome (simulate event closing)")
st.caption("In production this fills automatically when an officer closes an incident. "
           "Here you can simulate it to watch the system learn.")
con = sqlite3.connect(str(LEARNING_DB_PATH))
preds = pd.read_sql(
    """SELECT prediction_id, corridor, pred_severity, pred_duration FROM predictions
       WHERE prediction_id NOT IN (SELECT prediction_id FROM outcomes)
       ORDER BY prediction_id DESC LIMIT 25""", con)
con.close()

if len(preds):
    with st.form("rec_outcome"):
        pid = st.selectbox("Open prediction", preds["prediction_id"],
            format_func=lambda x: f"#{x} · {preds.loc[preds.prediction_id==x,'corridor'].values[0]} · "
                                  f"pred {preds.loc[preds.prediction_id==x,'pred_severity'].values[0]} "
                                  f"{preds.loc[preds.prediction_id==x,'pred_duration'].values[0]:.0f}m")
        oa, ob = st.columns(2)
        actual_sev = oa.selectbox("Actual severity", ["High", "Medium", "Low"])
        actual_dur = ob.number_input("Actual clearance (min)", min_value=1.0, value=90.0, step=5.0)
        if st.form_submit_button("Record outcome", use_container_width=True):
            res = learning.record_outcome(int(pid), actual_severity=actual_sev, actual_duration_mins=actual_dur)
            ok = "✅ correct" if res["severity_correct"] else "❌ wrong"
            st.success(f"Recorded · severity {ok} · duration error {res['duration_error_mins']:.0f} min")
            st.rerun()
else:
    st.info("No open predictions. Make some on the Simulator or Copilot pages first.", icon="🔮")
