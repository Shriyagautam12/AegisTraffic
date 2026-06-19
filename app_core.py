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
/* ---- Base: LIGHT theme ---- */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', system-ui, sans-serif; }

.stApp {
    background: #f7f7f4;            /* warm off-white */
    color: #1f2430;
}
.block-container { padding-top: 2.2rem; }

/* ---- Hide default chrome ---- */
#MainMenu, footer, header { visibility: hidden; }

/* ---- Sidebar ---- */
section[data-testid="stSidebar"] {
    background: #ffffff;
    border-right: 1px solid #ececec;
}
section[data-testid="stSidebar"] * { color: #1f2430; }

/* ---- Sidebar toggle — always visible, amber pill ---- */
button[data-testid="collapsedControl"],
button[data-testid="baseButton-headerNoPadding"] {
    background: #e8932e !important;
    color: #fff !important;
    border-radius: 0 10px 10px 0 !important;
    width: 28px !important;
    height: 48px !important;
    top: 50% !important;
    left: 0 !important;
    position: fixed !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    opacity: 1 !important;
    z-index: 999999 !important;
    box-shadow: 3px 0 12px rgba(232,147,46,0.4) !important;
    border: none !important;
    cursor: pointer !important;
}
button[data-testid="collapsedControl"]:hover,
button[data-testid="baseButton-headerNoPadding"]:hover {
    background: #f5b840 !important;
    box-shadow: 4px 0 16px rgba(245,184,64,0.5) !important;
}
/* Also ensure the expand arrow inside sidebar is always visible */
[data-testid="stSidebarCollapseButton"] button {
    opacity: 1 !important;
    color: #9aa0ab !important;
}

/* ---- Title ---- */
.aegis-title {
    font-size: 2.5rem; font-weight: 800; letter-spacing: -1px; color:#1f2430;
}
.aegis-sub { color:#8a909c; font-size:1.02rem; margin-top:-4px; }

/* ---- Brand block (sidebar) ---- */
.brand-row { display:flex; align-items:center; gap:12px; margin:2px 0 18px 0; }
.brand-logo {
    width:42px; height:42px; border-radius:12px;
    background: linear-gradient(150deg,#f5b840,#e8932e);
    display:flex; align-items:center; justify-content:center; font-size:1.4rem;
    box-shadow:0 4px 14px rgba(232,147,46,.35);
}
.brand-name { font-weight:800; font-size:1.15rem; color:#1f2430; line-height:1; }
.brand-tag  { font-size:.72rem; color:#9aa0ab; margin-top:3px; }

/* ---- Metric cards (white, soft shadow) ---- */
.metric-card {
    background: #ffffff;
    border: 1px solid #ededed;
    border-radius: 18px; padding: 18px 20px;
    box-shadow: 0 6px 22px rgba(31,36,48,0.05);
    transition: transform .22s ease, box-shadow .22s ease;
    animation: rise .5s ease both;
}
.metric-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 14px 34px rgba(31,36,48,0.12);
}
.metric-value { font-size: 2.0rem; font-weight: 800; line-height:1; color:#1f2430; }
.metric-label { color:#9aa0ab; font-size:.78rem; margin-top:8px; text-transform:uppercase; letter-spacing:.7px; font-weight:600;}
@keyframes rise { from { opacity:0; transform: translateY(12px);} to {opacity:1; transform:none;} }

/* ---- Severity badges ---- */
.badge { display:inline-block; padding:6px 16px; border-radius:999px; font-weight:700; font-size:1rem;
         animation: pop .4s cubic-bezier(.2,1.4,.4,1) both; }
.badge-high   { background:#fdeceb; color:#d6453b; border:1px solid #f3b6b1; }
.badge-medium { background:#fdf4e3; color:#c9890f; border:1px solid #f1d79b; }
.badge-low    { background:#e9f7ee; color:#2f9e57; border:1px solid #b6e3c6; }
@keyframes pop { from{opacity:0; transform:scale(.7);} to{opacity:1; transform:scale(1);} }

/* ---- Pulse dot ---- */
.pulse { display:inline-block; width:9px; height:9px; border-radius:50%; background:#2f9e57; margin-right:7px;
         box-shadow:0 0 0 0 rgba(47,158,87,.55); animation:pulse 1.8s infinite; }
@keyframes pulse { 70%{box-shadow:0 0 0 10px rgba(47,158,87,0);} 100%{box-shadow:0 0 0 0 rgba(47,158,87,0);} }

/* ---- Section headers ---- */
.section-h { font-size:1.15rem; font-weight:700; color:#1f2430; margin: 4px 0 8px 0;
             border-left:3px solid #2f9e57; padding-left:10px; }

/* ---- Buttons (amber primary) ---- */
.stButton>button {
    background: linear-gradient(150deg,#f5b840,#e8932e); color:#fff; border:none;
    border-radius:12px; padding:.55rem 1.1rem; font-weight:700;
    transition: transform .15s ease, box-shadow .2s ease;
}
.stButton>button:hover { transform: translateY(-2px); box-shadow:0 8px 22px rgba(232,147,46,.4); }

/* ---- Reason chips ---- */
.chip { display:inline-block; background:#fdf4e3; border:1px solid #f1d79b;
        color:#a96f0c; padding:5px 12px; border-radius:10px; margin:4px 6px 0 0; font-size:.85rem;}

/* ---- Chat bubbles ---- */
.bubble-user { background:linear-gradient(150deg,#f5b840,#e8932e); color:#fff; padding:12px 16px;
               border-radius:16px 16px 4px 16px; margin:6px 0; max-width:80%; margin-left:auto; }
.bubble-ai   { background:#ffffff; border:1px solid #ededed; color:#1f2430;
               padding:12px 16px; border-radius:16px 16px 16px 4px; margin:6px 0; max-width:88%;
               box-shadow:0 4px 14px rgba(31,36,48,0.05); }

/* ---- Circular activity gauge ---- */
.gauge-wrap { display:flex; flex-direction:column; align-items:center; padding:8px 0 4px; }
.gauge {
    width:170px; height:170px; border-radius:50%;
    display:flex; align-items:center; justify-content:center;
    animation: rise .6s ease both;
}
.gauge-inner {
    width:128px; height:128px; border-radius:50%; background:#ffffff;
    display:flex; flex-direction:column; align-items:center; justify-content:center;
}
.gauge-pct { font-size:2.4rem; font-weight:800; line-height:1; }
.gauge-lvl { font-size:.8rem; font-weight:700; letter-spacing:1.5px; margin-top:4px; }
.gauge-cap { color:#9aa0ab; font-size:.78rem; text-transform:uppercase; letter-spacing:.7px;
             text-align:center; margin-top:12px; font-weight:600; }
.gauge-when { color:#1f2430; font-weight:700; text-align:center; margin-top:10px; }
</style>
"""


def inject_theme():
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    # Ensure sidebar toggle button is always rendered even when collapsed
    st.markdown("""
    <script>
    const observer = new MutationObserver(() => {
        const btn = document.querySelector('button[data-testid="collapsedControl"]');
        if (btn) { btn.style.opacity = '1'; btn.style.display = 'flex'; }
    });
    observer.observe(document.body, {childList: true, subtree: true});
    </script>
    """, unsafe_allow_html=True)


def sidebar_brand():
    """Render the AegisTraffic brand block at the top of the sidebar."""
    st.markdown(
        """<div class="brand-row">
            <div class="brand-logo">🛡️</div>
            <div>
                <div class="brand-name">AegisTraffic</div>
                <div class="brand-tag">Bengaluru Traffic Command</div>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )


def activity_gauge(pct: float, level: str, when: str = ""):
    """Circular ring gauge (amber→coral) showing % of peak + level label."""
    pct = max(0.0, min(1.0, pct))
    deg = int(pct * 360)
    color = {"HIGH": "#d6453b", "MODERATE": "#e8932e", "LOW": "#2f9e57"}.get(level, "#e8932e")
    ring = f"conic-gradient({color} {deg}deg, #ededed {deg}deg)"
    when_html = f'<div class="gauge-when">{when}</div>' if when else ""
    return f"""
    <div class="gauge-wrap">
      <div class="gauge" style="background:{ring}">
        <div class="gauge-inner">
          <div class="gauge-pct" style="color:{color}">{pct*100:.0f}<span style="font-size:1.1rem">%</span></div>
          <div class="gauge-lvl" style="color:{color}">{level}</div>
        </div>
      </div>
      {when_html}
      <div class="gauge-cap">City-wide activity</div>
    </div>
    """


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
