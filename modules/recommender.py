"""
Module 4 — Resource Recommendation Engine
Turns a prediction (severity / cause / corridor / vehicle / road-closure) into a
concrete, data-grounded deployment plan: officers, barricades, tow vehicles,
WHICH junctions to deploy at, and WHICH police station owns the corridor.

Design principle: every number is traceable. Officer counts come from a
transparent formula; deployment junctions and the owning police station come
from the ACTUAL historical incident data (not invented).
"""

import json
import math
import urllib.request

import pandas as pd
from modules.data_pipeline import load_data, norm_cat

# Public OSRM demo server (free, no API key). Used only on explicit request.
OSRM_BASE = "http://router.project-osrm.org/route/v1/driving"
OSRM_TIMEOUT = 5  # seconds

# ── Officer formula ─────────────────────────────────────────────────────────────
# base by severity, scaled by corridor class, plus a road-closure bonus.
BASE_OFFICERS = {"High": 4, "Medium": 2, "Low": 1}

# Corridor class multiplier — CBD (dense core) needs more bodies per incident
CBD_CORRIDORS = {"cbd 1", "cbd 2"}
ORR_PREFIX    = "orr"   # outer ring road corridors

ROAD_CLOSURE_OFFICER_BONUS = 2

# ── Tow vehicle rules ───────────────────────────────────────────────────────────
HEAVY_VEH = {"heavy_vehicle", "truck", "bmtc_bus", "ksrtc_bus"}
MED_VEH   = {"lcv", "private_bus"}

# ── Causes that imply specific equipment ────────────────────────────────────────
TREE_CAUSES   = {"tree_fall"}
WATER_CAUSES  = {"water_logging"}
DEBRIS_CAUSES = {"debris", "pot_holes", "road_conditions"}


class ResourceRecommender:
    """
    Instantiate once. Call recommend(event, severity) per prediction.
    Junction/station lookups are precomputed from historical data at init.
    """

    def __init__(self, df: pd.DataFrame = None):
        self.df = df if df is not None else load_data()
        self._corridor_junctions = self._build_corridor_junctions()
        self._corridor_station   = self._build_corridor_station()
        self._corridor_centroids = self._build_corridor_centroids()

    def _build_corridor_centroids(self) -> dict:
        """Real corridor centroids = mean incident coordinate per corridor.
        Computed from data (not hardcoded). Used for diversion bypass waypoints."""
        valid = self.df[
            (self.df["latitude"] != 0) & (self.df["longitude"] != 0) &
            self.df["latitude"].notna() & self.df["longitude"].notna()
        ]
        out = {}
        for corridor, grp in valid.groupby("corridor_norm"):
            if len(grp) >= 5:   # need enough points for a stable centroid
                out[corridor] = (float(grp["latitude"].mean()),
                                 float(grp["longitude"].mean()))
        return out

    # ── Precompute data-grounded lookups ────────────────────────────────────────

    def _build_corridor_junctions(self) -> dict:
        """For each corridor → ordered list of its busiest named junctions."""
        jdf = self.df[self.df["junction"].notna() & (self.df["junction"] != "")]
        out = {}
        for corridor, grp in jdf.groupby("corridor_norm"):
            top = grp["junction"].value_counts().head(5).index.tolist()
            out[corridor] = top
        return out

    def _build_corridor_station(self) -> dict:
        """For each corridor → the police station that handles it most often."""
        sdf = self.df[self.df["police_station"].notna()]
        out = {}
        for corridor, grp in sdf.groupby("corridor_norm"):
            counts = grp["police_station"].value_counts()
            if len(counts):
                out[corridor] = counts.index[0]
        return out

    # ── Core recommendation ─────────────────────────────────────────────────────

    def _officer_count(self, severity: str, corridor_norm: str,
                       road_closure: bool) -> tuple:
        """Return (count, breakdown_string) — fully traceable."""
        base = BASE_OFFICERS.get(severity, 1)

        if corridor_norm in CBD_CORRIDORS:
            mult, mult_label = 1.5, "CBD x1.5"
        elif corridor_norm.startswith(ORR_PREFIX):
            mult, mult_label = 1.25, "ORR x1.25"
        else:
            mult, mult_label = 1.0, "standard x1.0"

        count = round(base * mult)
        parts = [f"{base} base ({severity})", mult_label]
        if road_closure:
            count += ROAD_CLOSURE_OFFICER_BONUS
            parts.append(f"+{ROAD_CLOSURE_OFFICER_BONUS} road-closure")
        breakdown = " · ".join(parts) + f" = {count}"
        return count, breakdown

    def _tow_vehicles(self, veh_type: str, severity: str) -> int:
        if veh_type in HEAVY_VEH:
            return 1
        if veh_type in MED_VEH and severity == "High":
            return 1
        return 0

    def _barricades(self, severity: str, road_closure: bool) -> int:
        if road_closure:
            return 2
        if severity == "High":
            return 1
        return 0

    def _special_equipment(self, cause: str) -> list:
        eq = []
        if cause in TREE_CAUSES:
            eq.append("Tree-cutting crew + crane")
        if cause in WATER_CAUSES:
            eq.append("Water pump / de-watering unit")
        if cause in DEBRIS_CAUSES:
            eq.append("Debris-clearing crew")
        return eq

    def recommend(self, event: dict, severity: str = None) -> dict:
        """
        Build the full deployment plan.

        event keys used: event_cause, corridor, veh_type, requires_road_closure
        severity: pass the model's predicted severity (High/Medium/Low).
                  If None, defaults to Medium.
        """
        severity      = severity or "Medium"
        corridor_disp = event.get("corridor") or "Non-corridor"
        corridor_norm = norm_cat(corridor_disp) or "non-corridor"
        cause         = norm_cat(event.get("event_cause")) or "others"
        veh_type      = norm_cat(event.get("veh_type")) or "others"
        road_closure  = bool(event.get("requires_road_closure"))

        officers, officer_breakdown = self._officer_count(
            severity, corridor_norm, road_closure
        )
        tow        = self._tow_vehicles(veh_type, severity)
        barricades = self._barricades(severity, road_closure)
        equipment  = self._special_equipment(cause)

        # Data-grounded deployment locations
        junctions = self._corridor_junctions.get(corridor_norm, [])
        # how many deployment points scale with severity
        n_points = {"High": 3, "Medium": 2, "Low": 1}.get(severity, 1)
        deploy_at = junctions[:n_points] if junctions else ["(no named junction on record — deploy at incident point)"]

        station = self._corridor_station.get(corridor_norm, "Nearest available station")

        return {
            "severity":          severity,
            "officers":          officers,
            "officer_breakdown": officer_breakdown,
            "barricades":        barricades,
            "tow_vehicles":      tow,
            "special_equipment": equipment,
            "deploy_at":         deploy_at,
            "primary_junction":  deploy_at[0] if deploy_at else None,
            "owning_station":    station,
            "road_closure":      road_closure,
        }

    # ── Diversion routing (OSRM) — OPT-IN, isolated from recommend() ────────────
    # Deliberately NOT called inside recommend(): a live network call must never
    # sit in the prediction critical path during a demo. Call this only when the
    # user explicitly requests a diversion route. Always degrades gracefully.

    @staticmethod
    def _haversine_km(a: tuple, b: tuple) -> float:
        """Great-circle distance in km between two (lat, lon) points."""
        R = 6371.0
        lat1, lon1, lat2, lon2 = map(math.radians, [a[0], a[1], b[0], b[1]])
        dlat, dlon = lat2 - lat1, lon2 - lon1
        h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return 2 * R * math.asin(math.sqrt(h))

    def _osrm_route(self, coords: list) -> dict:
        """
        Call public OSRM for a route through the given [(lat,lon), ...] waypoints.
        Returns {duration_mins, distance_km, geometry} or {} on any failure.
        """
        coord_str = ";".join(f"{lon},{lat}" for lat, lon in coords)
        url = f"{OSRM_BASE}/{coord_str}?overview=full&geometries=geojson&alternatives=false"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AegisTraffic"})
            with urllib.request.urlopen(req, timeout=OSRM_TIMEOUT) as resp:
                data = json.loads(resp.read().decode())
            if data.get("code") == "Ok" and data.get("routes"):
                r = data["routes"][0]
                return {
                    "duration_mins": round(r["duration"] / 60.0, 1),
                    "distance_km":   round(r["distance"] / 1000.0, 2),
                    "geometry":      r["geometry"],   # GeoJSON LineString
                }
        except Exception:
            pass
        return {}

    def nearest_alternate_corridor(self, corridor: str,
                                   incident_coords: tuple) -> tuple:
        """Find the closest OTHER corridor centroid to the incident (real data)."""
        cur = norm_cat(corridor)
        best_name, best_coords, best_dist = None, None, float("inf")
        for name, coords in self._corridor_centroids.items():
            if name == cur:
                continue
            d = self._haversine_km(incident_coords, coords)
            if d < best_dist:
                best_name, best_coords, best_dist = name, coords, d
        return best_name, best_coords, (round(best_dist, 2) if best_name else None)

    def diversion_plan(self, event: dict, origin: tuple, dest: tuple) -> dict:
        """
        OPT-IN diversion computation. Returns normal + diverted routes via OSRM,
        bypassing through the nearest alternate corridor. Network-dependent —
        returns {available: False, reason: ...} if OSRM is unreachable.
        """
        corridor = event.get("corridor") or "Non-corridor"
        incident_coords = (event.get("latitude"), event.get("longitude"))
        have_incident = incident_coords[0] is not None and incident_coords[1] is not None

        normal = self._osrm_route([origin, dest])
        if not normal:
            return {"available": False, "reason": "OSRM unreachable (check network)"}

        result = {
            "available":          True,
            "normal_route":       normal,
            "diverted_route":     None,
            "alternate_corridor": None,
            "alternate_distance_km": None,
            "time_penalty_mins":  None,
        }

        # Only compute a bypass if a closure is required and we know where it is
        if event.get("requires_road_closure") and have_incident:
            alt_name, alt_coords, alt_dist = self.nearest_alternate_corridor(
                corridor, incident_coords
            )
            if alt_coords:
                diverted = self._osrm_route([origin, alt_coords, dest])
                if diverted:
                    result["diverted_route"]        = diverted
                    result["alternate_corridor"]    = alt_name.title()
                    result["alternate_distance_km"] = alt_dist
                    result["time_penalty_mins"]     = round(
                        diverted["duration_mins"] - normal["duration_mins"], 1
                    )
        return result

    def format_text(self, plan: dict) -> str:
        """Human-readable deployment directive (for copilot / dashboard)."""
        lines = [
            f"DEPLOYMENT PLAN ({plan['severity']} severity)",
            f"  Officers:   {plan['officers']}   [{plan['officer_breakdown']}]",
            f"  Barricades: {plan['barricades']} set(s)",
            f"  Tow:        {'Yes (' + str(plan['tow_vehicles']) + ')' if plan['tow_vehicles'] else 'Not required'}",
        ]
        if plan["special_equipment"]:
            lines.append(f"  Equipment:  {', '.join(plan['special_equipment'])}")
        lines.append(f"  Deploy at:  {', '.join(plan['deploy_at'])}")
        lines.append(f"  Station:    {plan['owning_station']}")
        return "\n".join(lines)
