"""
Module 3 — Similar Event Retrieval Engine
Given a new event, finds the most similar historical CLOSED incidents and
shows what actually happened (real closure times, dates, outcomes).

Explainability through evidence: a traffic officer trusts a real precedent
("last procession on Mysore Road closed the road for 94 min") more than a
model score.

Design: cosine similarity over a normalized feature vector of CONTINUOUS and
ORDINAL features only (scores, tiers, time). Arbitrary category codes are
excluded — exact corridor/cause relevance is handled by the prefilter instead.
NO FAISS / no sentence-transformers — at ~8k rows, sklearn cosine is ~6ms.
"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity

from modules.data_pipeline import load_data, norm_cat

# ── Similarity feature vector + per-feature weights ─────────────────────────────
# We use ONLY continuous / ordinal / scored features here. Raw category codes
# (corridor_enc, event_cause_enc, zone_enc) are deliberately EXCLUDED: their
# integer values are arbitrary labels, so scaling them into a cosine distance
# injects meaningless "0 is close to 1" noise. Exact corridor/cause relevance is
# already guaranteed by the prefilter step, so we lose nothing by dropping them.
SIM_FEATURES = {
    "cause_score":        2.5,   # event cause impact rank (ordinal)
    "corridor_tier":      2.0,   # corridor historical risk tier (ordinal)
    "veh_risk":           1.5,   # vehicle class risk score (ordinal)
    "hour":               1.5,   # time of day (0-23, continuous)
    "day_of_week":        1.0,   # weekday pattern (0-6)
    "is_weekend":         0.5,
    "is_peak":            0.5,
    "priority_num":       1.0,
    "road_closure_num":   1.5,
}


class SimilarEventEngine:
    """
    Loads closed incidents once, builds a scaled+weighted feature matrix, and
    answers similarity queries. Instantiate once at app startup.
    """

    def __init__(self, df: pd.DataFrame = None):
        full = df if df is not None else load_data()
        # Only events with known outcomes are useful as precedent
        self.df = full[
            full["status"].isin(["closed", "resolved"])
        ].dropna(subset=["start_datetime"]).reset_index(drop=True)

        self.feature_names = list(SIM_FEATURES.keys())
        self.weights = np.array([SIM_FEATURES[f] for f in self.feature_names])

        # Build scaled feature matrix
        raw = self.df[self.feature_names].fillna(0).astype(float).values
        self.scaler = StandardScaler()
        scaled = self.scaler.fit_transform(raw)
        self.matrix = scaled * self.weights   # apply weights post-scaling

    # ── Build a query vector from a raw event dict ──────────────────────────────

    def _event_to_vector(self, event: dict) -> np.ndarray:
        """
        Convert a raw event dict to a scaled+weighted query vector.
        Uses pure ordinal / risk mappings — no arbitrary category codes — so the
        cosine distance is mathematically meaningful. No DataFrame lookups, O(1).
        """
        from modules.data_pipeline import (
            CAUSE_SEVERITY_SCORE_NORM, CORRIDOR_RISK_TIER_NORM, VEH_RISK_SCORE_NORM,
            PEAK_HOURS,
        )
        cause    = norm_cat(event.get("event_cause")) or "others"
        corridor = norm_cat(event.get("corridor")) or "non-corridor"
        veh_type = norm_cat(event.get("veh_type")) or "others"
        hour     = int(event.get("hour", 12))
        dow      = int(event.get("day_of_week", 0))

        row = {
            "cause_score":      CAUSE_SEVERITY_SCORE_NORM.get(cause, 1),
            "corridor_tier":    CORRIDOR_RISK_TIER_NORM.get(corridor, 1),
            "veh_risk":         VEH_RISK_SCORE_NORM.get(veh_type, 1),
            "hour":             hour,
            "day_of_week":      dow,
            "is_weekend":       1 if dow >= 5 else 0,
            "is_peak":          1 if hour in PEAK_HOURS else 0,
            "priority_num":     1 if event.get("priority") == "High" else 0,
            "road_closure_num": 1 if event.get("requires_road_closure") else 0,
        }
        vec = np.array([row[f] for f in self.feature_names], dtype=float).reshape(1, -1)
        scaled = self.scaler.transform(vec)
        return scaled * self.weights

    # ── Public API ──────────────────────────────────────────────────────────────

    def find_similar(self, event: dict, k: int = 5,
                     prefilter: bool = True) -> list:
        """
        Return the top-k most similar historical closed incidents.

        prefilter=True restricts the candidate pool to the same corridor OR same
        cause first (keeps results operationally relevant), then ranks by cosine
        similarity. Falls back to the full pool if the prefilter is too narrow.
        """
        query = self._event_to_vector(event)

        # Candidate pool
        idx = np.arange(len(self.df))
        if prefilter:
            cause    = norm_cat(event.get("event_cause"))
            corridor = norm_cat(event.get("corridor"))
            mask = pd.Series(False, index=self.df.index)
            if cause is not None:
                mask |= (self.df["event_cause"] == cause)
            if corridor is not None:
                mask |= (self.df["corridor_norm"] == corridor)
            if mask.sum() >= k:        # only use prefilter if it leaves enough
                idx = np.where(mask.values)[0]

        with np.errstate(all="ignore"):
            sims = cosine_similarity(query, self.matrix[idx])[0]
        sims = np.nan_to_num(sims, nan=0.0)
        order = np.argsort(sims)[::-1][:k]
        top_idx = idx[order]
        top_sims = sims[order]

        results = []
        for rank, (i, sim) in enumerate(zip(top_idx, top_sims), start=1):
            row = self.df.iloc[i]
            results.append({
                "rank":            rank,
                "similarity":      round(float(sim), 3),
                "id":              row["id"],
                "date":            row["start_datetime"].strftime("%d %b %Y")
                                   if pd.notna(row["start_datetime"]) else "—",
                "day":             row["day_name"] if pd.notna(row.get("day_name")) else "—",
                "event_cause":     row["event_cause"],
                "corridor":        row["corridor"],
                "junction":        row["junction"] if pd.notna(row["junction"]) else "—",
                "zone":            row["zone"] if pd.notna(row["zone"]) else "—",
                "severity":        row["severity"],
                "road_closure":    bool(row["requires_road_closure"]),
                "closure_mins":    round(float(row["closure_mins"]), 1)
                                   if pd.notna(row["closure_mins"]) else None,
                "police_station":  row["police_station"] if pd.notna(row["police_station"]) else "—",
                "veh_type":        row["veh_type"] if pd.notna(row["veh_type"]) else "—",
            })
        return results

    def summarize_precedent(self, event: dict, k: int = 5) -> dict:
        """
        Aggregate stats over the k similar events — used by the copilot and the
        dashboard to say 'historically, similar events closed in ~X min'.

        Reports MEDIAN as the headline 'typical' closure (robust to the
        multi-day chronic outliers in the data). Mean is capped at 24h so a
        single waterlogging event can't blow up the average.
        """
        similar = self.find_similar(event, k=k)
        closures = [s["closure_mins"] for s in similar if s["closure_mins"] is not None]
        high_ct  = sum(1 for s in similar if s["severity"] == "High")
        closed_ct = sum(1 for s in similar if s["road_closure"])

        # Cap individual closures at 24h BEFORE aggregating — a multi-day chronic
        # event shouldn't define the "typical" operational response time.
        capped = [min(c, 1440) for c in closures]
        typical_closure = round(float(np.median(capped)), 1) if capped else None
        mean_capped     = round(float(np.mean(capped)), 1) if capped else None

        # Confidence flag: did enough similar events have real closure data?
        low_confidence = len(closures) < 3

        return {
            "n_similar":            len(similar),
            "typical_closure_mins": typical_closure,   # headline — capped median
            "mean_closure_capped":  mean_capped,
            "n_with_closure":       len(closures),
            "low_confidence":       low_confidence,     # True if <3 data points
            "high_severity_count":  high_ct,
            "road_closure_count":   closed_ct,
            "similar_events":       similar,
        }
