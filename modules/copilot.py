"""
Module 6 — AI Traffic Command Copilot (RAG + Gemini)
Natural-language interface for traffic operators. Parses a free-text query
(English or Kannada), assembles grounded CONTEXT from Modules 1-4, and asks
Gemini to phrase an operational answer.

Key principle: Gemini never invents traffic facts. All numbers/precedents come
from our own modules; the LLM only reasons over and phrases that context.
Falls back to a structured (non-LLM) answer if Gemini is unavailable.
"""

import os
import json
import re

from modules.data_pipeline import norm_cat

# Gemini is optional at import time; only needed for the LLM phrasing step.
try:
    import google.generativeai as genai
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False

GEMINI_MODEL = "gemini-3.5-flash"   # fast, low-cost; Kannada-capable

# Known categories for query parsing (kept in sync with the dataset)
KNOWN_CAUSES = [
    "vehicle_breakdown", "accident", "tree_fall", "water_logging", "pot_holes",
    "construction", "public_event", "procession", "vip_movement", "protest",
    "congestion", "road_conditions", "debris",
]
KNOWN_CORRIDORS = [
    "Mysore Road", "Bellary Road 1", "Bellary Road 2", "Tumkur Road",
    "Hosur Road", "ORR North 1", "ORR North 2", "ORR East 1", "ORR East 2",
    "ORR West 1", "Old Madras Road", "Magadi Road", "Bannerghatta Road",
    "CBD 1", "CBD 2", "Hennur Main Road", "Varthur Road", "Old Airport Road",
    "Airport New South Road", "West of Chord Road", "IRR(Thanisandra road)",
]

DAY_NAME_TO_NUM = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


class TrafficCopilot:
    """
    Orchestrates: parse query → assemble context → LLM phrasing.
    Depends on already-instantiated engines (predictor, retrieval, recommender,
    intelligence) so it reuses their loaded state.
    """

    def __init__(self, predictor, retriever, recommender, intelligence,
                 api_key: str = None):
        self.predictor    = predictor
        self.retriever    = retriever
        self.recommender  = recommender
        self.intelligence = intelligence

        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.llm = None
        if _GENAI_AVAILABLE and self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self.llm = genai.GenerativeModel(GEMINI_MODEL)
            except Exception:
                self.llm = None

    # ── Step 1: Parse the free-text query into structured fields ────────────────

    def parse_query(self, query: str) -> dict:
        """
        Rule-based extraction of event_cause, corridor, hour, day from text.
        Works for English + transliterated terms. (Deliberately not LLM-based so
        parsing works even offline / without an API key.)
        """
        q = query.lower()
        event = {}

        # cause — match known causes and common synonyms
        cause_synonyms = {
            "procession": "procession", "rally": "procession", "march": "procession",
            "festival": "public_event", "event": "public_event", "match": "public_event",
            "concert": "public_event", "cricket": "public_event", "ipl": "public_event",
            "vip": "vip_movement", "convoy": "vip_movement",
            "protest": "protest", "strike": "protest", "dharna": "protest",
            "breakdown": "vehicle_breakdown", "broken down": "vehicle_breakdown",
            "accident": "accident", "collision": "accident", "crash": "accident",
            "tree": "tree_fall", "waterlog": "water_logging", "flood": "water_logging",
            "rain": "water_logging", "pothole": "pot_holes", "construction": "construction",
            "roadwork": "construction", "digging": "construction",
        }
        for kw, cause in cause_synonyms.items():
            if kw in q:
                event["event_cause"] = cause
                break

        # corridor — substring match against known corridors
        for corridor in KNOWN_CORRIDORS:
            if norm_cat(corridor) in q:
                event["corridor"] = corridor
                break
        # also catch bare "mysore", "hosur", "tumkur" etc.
        if "corridor" not in event:
            for corridor in KNOWN_CORRIDORS:
                first_word = norm_cat(corridor).split()[0]
                if len(first_word) > 4 and first_word in q:
                    event["corridor"] = corridor
                    break

        # day of week
        for day, num in DAY_NAME_TO_NUM.items():
            if day in q:
                event["day_of_week"] = num
                break
        if "tomorrow" in q or "weekend" in q:
            event.setdefault("day_of_week", 5)

        # hour — explicit time like "6pm", "18:00", "9 pm"
        m = re.search(r"(\d{1,2})\s*(am|pm)", q)
        if m:
            hr = int(m.group(1)) % 12
            if m.group(2) == "pm":
                hr += 12
            event["hour"] = hr
        elif re.search(r"\bnight\b", q):
            event["hour"] = 21
        elif re.search(r"\bevening\b", q):
            event["hour"] = 19
        elif re.search(r"\bmorning\b", q):
            event["hour"] = 8
        elif re.search(r"\bafternoon\b", q):
            event["hour"] = 14

        # road closure hint
        if any(w in q for w in ["close", "closure", "block", "barricade", "divert"]):
            event["requires_road_closure"] = True

        # priority hint
        if "vip_movement" in event.values() or event.get("event_cause") == "vip_movement":
            event["priority"] = "High"

        return event

    # ── Step 2: Assemble grounded context from all modules ──────────────────────

    def assemble_context(self, event: dict) -> dict:
        """Gather prediction + precedent + resources + corridor stats."""
        ctx = {"parsed_event": event}

        # Prediction (Module 2)
        try:
            pred = self.predictor.predict(event)
            ctx["prediction"] = {
                "severity":      pred["severity"],
                "confidence":    pred["confidence"],
                "is_critical":   pred["is_critical"],
                "needs_attention": pred["needs_attention"],
                "duration_mins": pred["duration_mins"],
                "duration_range": pred["duration_range"],
                "top_reasons":   [r["feature"] for r in pred["top_reasons"]],
            }
        except Exception as e:
            ctx["prediction"] = {"error": str(e)}

        # Precedent (Module 3)
        try:
            summ = self.retriever.summarize_precedent(event, k=5)
            ctx["precedent"] = {
                "typical_closure_mins": summ["typical_closure_mins"],
                "n_with_closure":       summ["n_with_closure"],
                "low_confidence":       summ["low_confidence"],
                "high_severity_count":  summ["high_severity_count"],
                "examples": [
                    {"date": s["date"], "cause": s["event_cause"],
                     "corridor": s["corridor"], "closure_mins": s["closure_mins"],
                     "severity": s["severity"]}
                    for s in summ["similar_events"][:3]
                ],
            }
        except Exception as e:
            ctx["precedent"] = {"error": str(e)}

        # Resources (Module 4)
        try:
            sev = ctx.get("prediction", {}).get("severity", "Medium")
            plan = self.recommender.recommend(event, severity=sev)
            ctx["resources"] = {
                "officers":    plan["officers"],
                "barricades":  plan["barricades"],
                "tow_vehicles": plan["tow_vehicles"],
                "deploy_at":   plan["deploy_at"],
                "station":     plan["owning_station"],
                "equipment":   plan["special_equipment"],
            }
        except Exception as e:
            ctx["resources"] = {"error": str(e)}

        # Corridor intelligence (Module 1)
        corridor = event.get("corridor")
        if corridor:
            try:
                ctx["corridor_intel"] = {
                    "risk_index": round(self.intelligence.get_corridor_risk(corridor), 3),
                    "peak_hours": self.intelligence.get_peak_hours_for_corridor(corridor),
                }
            except Exception:
                pass

        return ctx

    # ── Step 3: Phrase the answer (Gemini, or structured fallback) ──────────────

    def _build_prompt(self, query: str, ctx: dict) -> str:
        return f"""You are AegisTraffic, an AI command copilot for the Bengaluru Traffic Police.
You advise officers on traffic incident and event management. Be concise, operational, and confident.
You may receive queries in English or Kannada — reply in the same language as the query.

CRITICAL RULE: Use ONLY the data in the CONTEXT below. Do not invent statistics,
junction names, or closure times. If the context flags low confidence, say so.

CONTEXT (from AegisTraffic's models, grounded in 8,173 historical Bengaluru incidents):
{json.dumps(ctx, indent=2, default=str)}

OFFICER'S QUERY:
{query}

Write a short operational briefing (4-6 sentences) covering:
1. Predicted severity and expected impact duration
2. What history shows (cite the precedent closure time if available; note if low confidence)
3. Specific deployment recommendation (officers, where, station)
4. Any special equipment needed
Keep it practical — an officer should be able to act on it immediately."""

    def _fallback_answer(self, query: str, ctx: dict) -> str:
        """Structured answer assembled WITHOUT the LLM (offline-safe)."""
        pred = ctx.get("prediction", {})
        prec = ctx.get("precedent", {})
        res  = ctx.get("resources", {})
        ev   = ctx.get("parsed_event", {})

        lines = ["**AegisTraffic Briefing** (offline mode)\n"]
        cause = ev.get("event_cause", "event")
        corridor = ev.get("corridor", "the location")
        lines.append(f"Event: {cause} on {corridor}.")

        if "severity" in pred:
            lines.append(
                f"Predicted severity: **{pred['severity']}** "
                f"({int(pred['confidence']*100)}% confidence). "
                f"Estimated impact ~{pred['duration_mins']:.0f} min."
            )
        if prec.get("typical_closure_mins") is not None:
            conf = " (limited historical data — treat as indicative)" if prec.get("low_confidence") else ""
            lines.append(
                f"History: similar events typically cleared in "
                f"~{prec['typical_closure_mins']:.0f} min{conf}."
            )
        if "officers" in res:
            where = ", ".join(res["deploy_at"][:2])
            officer_word = "officer" if res["officers"] == 1 else "officers"
            lines.append(
                f"Recommended: deploy **{res['officers']} {officer_word}** at {where}; "
                f"{res['barricades']} barricade set(s); "
                f"coordinate via {res['station']}."
            )
            if res.get("equipment"):
                lines.append(f"Equipment: {', '.join(res['equipment'])}.")
        return "\n".join(lines)

    def ask(self, query: str) -> dict:
        """
        Main entry point. Returns the answer + the context used (transparency)
        + which path produced it (gemini / fallback).
        """
        event = self.parse_query(query)
        ctx = self.assemble_context(event)

        if self.llm is not None:
            try:
                prompt = self._build_prompt(query, ctx)
                resp = self.llm.generate_content(prompt)
                return {
                    "answer":  resp.text,
                    "source":  "gemini",
                    "context": ctx,
                    "parsed":  event,
                }
            except Exception as e:
                # graceful degradation
                return {
                    "answer":  self._fallback_answer(query, ctx),
                    "source":  f"fallback (gemini error: {e})",
                    "context": ctx,
                    "parsed":  event,
                }
        else:
            return {
                "answer":  self._fallback_answer(query, ctx),
                "source":  "fallback (no api key)",
                "context": ctx,
                "parsed":  event,
            }
