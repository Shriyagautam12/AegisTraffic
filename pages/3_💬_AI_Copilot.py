"""Page 3 — AI Copilot: natural-language traffic command assistant (Gemini + RAG)."""

import streamlit as st
from app_core import inject_theme, get_engines, section

st.set_page_config(page_title="AI Copilot — AegisTraffic", page_icon="💬", layout="wide")
inject_theme()

engines = get_engines()
copilot = engines["copilot"]
learning = engines["learning"]

st.markdown('<div class="aegis-title">💬 Ask AegisTraffic</div>', unsafe_allow_html=True)
mode = "Gemini (live)" if copilot.llm else "Offline (structured)"
st.markdown(f'<div class="aegis-sub"><span class="pulse"></span>Natural-language command copilot · '
            f'English & ಕನ್ನಡ · Mode: {mode}</div>', unsafe_allow_html=True)
st.write("")

EXAMPLES = [
    "Cricket match at Chinnaswamy, CBD 2, Friday 7pm with road closure. What should we do?",
    "There is a procession on Mysore Road tomorrow night.",
    "A truck has broken down on Tumkur Road this morning.",
    "VIP convoy on Bellary Road 1 at 10am.",
    "ನಾಳೆ ರಾತ್ರಿ ಮೈಸೂರು ರಸ್ತೆಯಲ್ಲಿ ಮೆರವಣಿಗೆ ಇದೆ. ಏನು ಮಾಡಬೇಕು?",
]

if "chat" not in st.session_state:
    st.session_state.chat = []

# ── Sidebar examples ─────────────────────────────────────────────────────────
with st.sidebar:
    section("Try an example")
    for ex in EXAMPLES:
        if st.button(ex, key=ex, use_container_width=True):
            st.session_state.pending = ex
    if st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state.chat = []

# ── Render history ───────────────────────────────────────────────────────────
for turn in st.session_state.chat:
    st.markdown(f'<div class="bubble-user">{turn["q"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="bubble-ai">{turn["a"]}</div>', unsafe_allow_html=True)
    if turn.get("source"):
        st.caption(f"🔎 {turn['source']} · grounded in: {turn.get('used','prediction + precedent + resources')}")

# ── Input ────────────────────────────────────────────────────────────────────
query = st.chat_input("Ask about an event, incident, or corridor…")
if "pending" in st.session_state and not query:
    query = st.session_state.pop("pending")

if query:
    st.markdown(f'<div class="bubble-user">{query}</div>', unsafe_allow_html=True)
    with st.spinner("AegisTraffic is analyzing…"):
        result = copilot.ask(query)
    st.markdown(f'<div class="bubble-ai">{result["answer"]}</div>', unsafe_allow_html=True)

    used = []
    ctx = result.get("context", {})
    if ctx.get("prediction"): used.append("ML prediction")
    if ctx.get("precedent", {}).get("examples"): used.append(f"{len(ctx['precedent']['examples'])} similar events")
    if ctx.get("resources"): used.append("resource plan")
    st.caption(f"🔎 {result['source']} · grounded in: {', '.join(used) or 'context'}")

    # log prediction if copilot parsed an event
    try:
        ev = result.get("parsed", {})
        if ev.get("corridor") and ctx.get("prediction", {}).get("severity"):
            learning.log_prediction(ev, ctx["prediction"])
    except Exception:
        pass

    st.session_state.chat.append({
        "q": query, "a": result["answer"], "source": result["source"],
        "used": ", ".join(used),
    })
