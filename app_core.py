"""
app_core.py — Engine loader for AegisTraffic FastAPI backend.

Loads all ML/AI engines once at startup and caches them.
The Streamlit UI helpers (inject_theme, sidebar_brand, etc.) are kept
below but only imported when Streamlit is available (legacy pages).
"""

from dotenv import load_dotenv
load_dotenv()


# ── Engine loader (used by main.py / FastAPI) ────────────────────────────────

_engines_cache = None

def get_engines():
    """
    Load all engines once and cache in module-level variable.
    Safe to call multiple times — returns same instance.
    """
    global _engines_cache
    if _engines_cache is not None:
        return _engines_cache

    from modules.data_pipeline import load_data
    from modules.intelligence import TrafficIntelligenceEngine
    from modules.predictor import ImpactPredictor
    from modules.retrieval import SimilarEventEngine
    from modules.recommender import ResourceRecommender
    from modules.copilot import TrafficCopilot
    from modules.learning import PostEventLearning

    df          = load_data()
    intel       = TrafficIntelligenceEngine(df)
    predictor   = ImpactPredictor()
    retriever   = SimilarEventEngine(df)
    recommender = ResourceRecommender(df)
    learning    = PostEventLearning()
    copilot     = TrafficCopilot(predictor, retriever, recommender, intel)

    _engines_cache = {
        "df": df, "intel": intel, "predictor": predictor,
        "retriever": retriever, "recommender": recommender,
        "copilot": copilot, "learning": learning,
    }
    return _engines_cache


# ── Streamlit helpers (legacy pages only — only imported when st is available) ──

try:
    import streamlit as st

    @st.cache_resource(show_spinner="Booting AegisTraffic engines…")
    def get_engines_st():
        """Streamlit-cached version for legacy .py pages."""
        return get_engines()

    THEME_CSS = """
<style>
/* ---- Base: LIGHT theme ---- */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', system-ui, sans-serif; }

.stApp {
    background: #f7f7f4;
    color: #1f2430;
}
.block-container { padding-top: 2.2rem; }
#MainMenu, footer, header { visibility: hidden; }

section[data-testid="stSidebar"] {
    background: #ffffff;
    border-right: 1px solid #ececec;
}
section[data-testid="stSidebar"] * { color: #1f2430; }
</style>
"""

    def inject_theme():
        st.markdown(THEME_CSS, unsafe_allow_html=True)

    def sidebar_brand():
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

    def section(title: str):
        st.markdown(f'<div class="section-h">{title}</div>', unsafe_allow_html=True)

    def severity_badge(severity: str):
        cls = {"High": "badge-high", "Medium": "badge-medium", "Low": "badge-low"}.get(severity, "badge-low")
        return f'<span class="badge {cls}">{severity.upper()}</span>'

    def metric_card(value, label, color="#60a5fa", delay=0.0):
        return f"""
    <div class="metric-card" style="animation-delay:{delay}s">
        <div class="metric-value" style="color:{color}">{value}</div>
        <div class="metric-label">{label}</div>
    </div>
    """

    def activity_gauge(pct: float, level: str, when: str = ""):
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

except ImportError:
    # Streamlit not installed (production FastAPI mode) — helpers not available
    pass
