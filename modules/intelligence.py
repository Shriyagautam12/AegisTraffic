"""
Module 1 — Historical Traffic Intelligence Engine
Produces precomputed intelligence artifacts consumed by all downstream modules.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from modules.data_pipeline import (
    load_data,
    get_corridor_stats,
    get_junction_stats,
    get_temporal_risk_matrix,
    norm_cat,
)

# ── Chronic chokepoint threshold ───────────────────────────────────────────────
# Junctions with median closure > this value are permanently flagged red
CHRONIC_THRESHOLD_MINS = 200

# ── Minimum incidents for a junction to appear in intelligence outputs ─────────
MIN_JUNCTION_INCIDENTS = 3


class TrafficIntelligenceEngine:
    """
    Loads historical data once and exposes all intelligence queries.
    Instantiate once at app startup; reuse across all modules.
    """

    def __init__(self, df: pd.DataFrame = None):
        self.df = df if df is not None else load_data()
        self._corridor_stats   = None
        self._junction_stats   = None
        self._temporal_matrix  = None
        self._corridor_lookup  = None
        self._junction_lookup  = None
        self._chronic_junctions = None
        self._cause_zone_map   = None
        self._build()

    # ── Internal build ─────────────────────────────────────────────────────────

    def _build(self):
        self._corridor_stats  = get_corridor_stats(self.df)
        self._junction_stats  = get_junction_stats(self.df)
        self._temporal_matrix = get_temporal_risk_matrix(self.df)

        # Fast O(1) lookup dicts — keyed by normalized corridor name so
        # "Mysore Road" and "mysore road" resolve to the same value.
        self._corridor_lookup = {
            norm_cat(c): v
            for c, v in zip(
                self._corridor_stats["corridor"],
                self._corridor_stats["corridor_risk_index"],
            )
        }
        self._junction_lookup = dict(
            zip(
                self._junction_stats["junction"],
                self._junction_stats["hotspot_score"],
            )
        )

        # Chronic chokepoints
        self._chronic_junctions = self._junction_stats[
            self._junction_stats["median_closure_mins"] >= CHRONIC_THRESHOLD_MINS
        ].copy()

        # Cause-zone affinity
        self._cause_zone_map = self._build_cause_zone_map()

    def _build_cause_zone_map(self) -> pd.DataFrame:
        """
        For each zone, compute the top 3 event causes by incident count.
        Used by the AI Copilot to give zone-aware advice.
        """
        df_valid = self.df[self.df["zone"].notna()].copy()
        grouped = (
            df_valid.groupby(["zone", "event_cause"])["id"]
            .count()
            .reset_index(name="count")
        )
        grouped["rank"] = grouped.groupby("zone")["count"].rank(
            ascending=False, method="first"
        )
        return grouped[grouped["rank"] <= 3].sort_values(["zone", "rank"])

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_corridor_risk(self, corridor: str) -> float:
        """Return risk index (0–1) for a named corridor. Case-insensitive.
        Default 0.3 if unknown."""
        return self._corridor_lookup.get(norm_cat(corridor), 0.3)

    def get_junction_hotspot_score(self, junction: str) -> float:
        """Return hotspot score (0–1) for a named junction. Default 0.2 if unknown."""
        return self._junction_lookup.get(junction, 0.2)

    def get_top_corridors(self, n: int = 10) -> pd.DataFrame:
        """Top N corridors by risk index."""
        return self._corridor_stats.head(n)[
            ["corridor", "incident_count", "median_closure_mins",
             "high_severity_rate", "road_closure_rate", "corridor_risk_index"]
        ]

    def get_top_junctions(self, n: int = 15) -> pd.DataFrame:
        """Top N junction hotspots."""
        return self._junction_stats.head(n)[
            ["junction", "incident_count", "median_closure_mins",
             "high_rate", "closure_rate", "hotspot_score", "lat", "lon"]
        ]

    def get_chronic_chokepoints(self) -> pd.DataFrame:
        """Junctions permanently flagged as chronic (median closure > threshold)."""
        return self._chronic_junctions[
            ["junction", "incident_count", "median_closure_mins",
             "hotspot_score", "lat", "lon"]
        ].sort_values("median_closure_mins", ascending=False)

    def get_risk_right_now(self, hour: int, day_of_week: int) -> float:
        """
        Returns the normalized risk score (0–1) for the given hour and day.
        Used for the live risk indicator on the dashboard.
        """
        try:
            return float(self._temporal_matrix.loc[hour, day_of_week])
        except KeyError:
            return 0.0

    def get_peak_hours_for_corridor(self, corridor: str, top_n: int = 3) -> list:
        """
        Returns the top N hours with most incidents on a given corridor.
        Used by the Copilot to say 'peak impact expected at 9PM'.
        """
        df_corr = self.df[self.df["corridor"] == corridor].dropna(subset=["hour"])
        if df_corr.empty:
            return []
        top_hours = (
            df_corr.groupby("hour")["id"]
            .count()
            .sort_values(ascending=False)
            .head(top_n)
            .index.tolist()
        )
        return [int(h) for h in top_hours]

    def get_cause_zone_summary(self, zone: str) -> list:
        """
        Returns top 3 event causes for a given zone.
        e.g. ['vehicle_breakdown', 'tree_fall', 'water_logging']
        """
        subset = self._cause_zone_map[self._cause_zone_map["zone"] == zone]
        return subset["event_cause"].tolist()

    def get_temporal_heatmap_data(self) -> pd.DataFrame:
        """Raw 24x7 normalized temporal matrix for map rendering."""
        return self._temporal_matrix

    def get_corridor_stats_full(self) -> pd.DataFrame:
        return self._corridor_stats

    def get_junction_stats_full(self) -> pd.DataFrame:
        return self._junction_stats

    def get_summary_stats(self) -> dict:
        """
        High-level summary numbers for the dashboard header cards.
        """
        df = self.df
        total      = len(df)
        high_count = (df["severity"] == "High").sum()
        planned    = (df["event_type"] == "planned").sum()
        unplanned  = (df["event_type"] == "unplanned").sum()
        chronic_ct = len(self._chronic_junctions)
        avg_closure = df["closure_mins"].median()

        return {
            "total_incidents":       int(total),
            "high_severity":         int(high_count),
            "high_severity_pct":     float(round(high_count / total * 100, 1)),
            "planned_events":        int(planned),
            "unplanned_events":      int(unplanned),
            "chronic_junctions":     int(chronic_ct),
            "median_closure_mins":   float(round(float(avg_closure), 1)),
            "corridors_monitored":   int(self._corridor_stats["corridor"].nunique()),
            "junctions_tracked":     int(self._junction_stats["junction"].nunique()),
        }

    def get_incidents_for_map(self) -> pd.DataFrame:
        """
        Returns all incidents with valid lat/lon for heatmap rendering.
        Includes severity and cause for popup display.
        """
        df = self.df[
            (self.df["latitude"] != 0) &
            (self.df["longitude"] != 0) &
            self.df["latitude"].notna() &
            self.df["longitude"].notna()
        ].copy()
        return df[[
            "id", "latitude", "longitude", "event_cause", "corridor",
            "junction", "severity", "closure_mins", "start_datetime",
            "event_type", "police_station", "zone", "requires_road_closure"
        ]]

    def get_similar_corridor_incidents(self, corridor: str,
                                       cause: str,
                                       limit: int = 20) -> pd.DataFrame:
        """
        Returns recent closed incidents on the same corridor with the same cause.
        Used by Module 3 as a fast pre-filter before cosine similarity.
        """
        df = self.df[
            (self.df["corridor"] == corridor) &
            (self.df["event_cause"] == cause) &
            (self.df["status"].isin(["closed", "resolved"]))
        ].copy()
        return df.sort_values("start_datetime", ascending=False).head(limit)
