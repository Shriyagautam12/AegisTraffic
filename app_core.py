"""
app_core.py — shared setup for the AegisTraffic dashboard.
Loads all engines once (cached), and provides the global theme/CSS + UI helpers.
"""

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── Cached engine loaders (load once per session, reused across pages) ──────────

@st.cache_resource(show_spinner="Booting AegisTraffic engines…")
def get_engines():
    from modules.data_pipeline import load_data
    from modules.intelligence import TrafficIntelligenceEngine
    from modules.predictor import ImpactPredictor
    from modules.retrieval import SimilarEventEngine
    from modules.recommender import ResourceRecommender
    from modules.copilot import TrafficCopilot
    from modules.learning import PostEventLearning

    df         = load_data()
    intel      = TrafficIntelligenceEngine(df)
    predictor  = ImpactPredictor()
    retriever  = SimilarEventEngine(df)
    recommender = ResourceRecommender(df)
    learning   = PostEventLearning()
    copilot    = TrafficCopilot(predictor, retriever, recommender, intel)

    return {
        "df": df, "intel": intel, "predictor": predictor,
        "retriever": retriever, "recommender": recommender,
        "copilot": copilot, "learning": learning,
    }


# ── Global theme / CSS ──────────────────────────────────────────────────────────

THEME_CSS = """
<style>
/* ---- Base ---- */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', system-ui, sans-serif; }

.stApp {
    background: radial-gradient(1200px 600px at 10% -10%, #16223a 0%, #0b1120 45%, #070b16 100%);
    color: #e8edf6;
}

/* ---- Hide default chrome ---- */
#MainMenu, footer, header { visibility: hidden; }

/* ---- Animated gradient title ---- */
.aegis-title {
    font-size: 2.6rem; font-weight: 800; letter-spacing: -1px;
    background: linear-gradient(90deg,#5eead4,#60a5fa,#a78bfa,#5eead4);
    background-size: 300% 100%;
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    animation: shimmer 6s linear infinite;
}
@keyframes shimmer { to { background-position: 300% 0; } }

.aegis-sub { color:#94a3b8; font-size:1.05rem; margin-top:-6px; }

/* ---- Metric cards ---- */
.metric-card {
    background: linear-gradient(160deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px; padding: 18px 20px; backdrop-filter: blur(6px);
    box-shadow: 0 8px 30px rgba(0,0,0,0.25);
    transition: transform .25s ease, box-shadow .25s ease, border-color .25s ease;
    animation: rise .6s ease both;
}
.metric-card:hover {
    transform: translateY(-6px);
    border-color: rgba(96,165,250,0.55);
    box-shadow: 0 14px 40px rgba(37,99,235,0.25);
}
.metric-value { font-size: 2.0rem; font-weight: 800; line-height:1; }
.metric-label { color:#9aa6bd; font-size:.85rem; margin-top:6px; text-transform:uppercase; letter-spacing:.6px;}
@keyframes rise { from { opacity:0; transform: translateY(14px);} to {opacity:1; transform:none;} }

/* ---- Severity badges ---- */
.badge { display:inline-block; padding:6px 16px; border-radius:999px; font-weight:700; font-size:1rem;
         animation: pop .4s cubic-bezier(.2,1.4,.4,1) both; }
.badge-high   { background:rgba(239,68,68,.18);  color:#fca5a5; border:1px solid #ef4444; }
.badge-medium { background:rgba(245,158,11,.18); color:#fcd34d; border:1px solid #f59e0b; }
.badge-low    { background:rgba(34,197,94,.16);  color:#86efac; border:1px solid #22c55e; }
@keyframes pop { from{opacity:0; transform:scale(.7);} to{opacity:1; transform:scale(1);} }

/* ---- Pulse dot ---- */
.pulse { display:inline-block; width:10px; height:10px; border-radius:50%; background:#22c55e; margin-right:8px;
         box-shadow:0 0 0 0 rgba(34,197,94,.7); animation:pulse 1.8s infinite; }
@keyframes pulse { 70%{box-shadow:0 0 0 12px rgba(34,197,94,0);} 100%{box-shadow:0 0 0 0 rgba(34,197,94,0);} }

/* ---- Section headers ---- */
.section-h { font-size:1.3rem; font-weight:700; color:#e8edf6; margin: 6px 0 2px 0;
             border-left:3px solid #60a5fa; padding-left:10px; }

/* ---- Buttons ---- */
.stButton>button {
    background: linear-gradient(90deg,#2563eb,#7c3aed); color:#fff; border:none;
    border-radius:12px; padding:.55rem 1.1rem; font-weight:700;
    transition: transform .15s ease, box-shadow .2s ease;
}
.stButton>button:hover { transform: translateY(-2px); box-shadow:0 8px 24px rgba(124,58,237,.4); }

/* ---- Reason chips ---- */
.chip { display:inline-block; background:rgba(96,165,250,.12); border:1px solid rgba(96,165,250,.35);
        color:#bfdbfe; padding:5px 12px; border-radius:10px; margin:4px 6px 0 0; font-size:.85rem;}

/* ---- Chat bubbles ---- */
.bubble-user { background:linear-gradient(135deg,#2563eb,#1d4ed8); color:#fff; padding:12px 16px;
               border-radius:16px 16px 4px 16px; margin:6px 0; max-width:80%; margin-left:auto; }
.bubble-ai   { background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.1); color:#e8edf6;
               padding:12px 16px; border-radius:16px 16px 16px 4px; margin:6px 0; max-width:88%; }
</style>
"""


def inject_theme():
    st.markdown(THEME_CSS, unsafe_allow_html=True)


def metric_card(value, label, color="#60a5fa", delay=0.0):
    return f"""
    <div class="metric-card" style="animation-delay:{delay}s">
        <div class="metric-value" style="color:{color}">{value}</div>
        <div class="metric-label">{label}</div>
    </div>
    """


def severity_badge(severity: str):
    cls = {"High": "badge-high", "Medium": "badge-medium", "Low": "badge-low"}.get(severity, "badge-low")
    return f'<span class="badge {cls}">{severity.upper()}</span>'


def section(title: str):
    st.markdown(f'<div class="section-h">{title}</div>', unsafe_allow_html=True)
