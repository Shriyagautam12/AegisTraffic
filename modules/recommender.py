import json
import math
import urllib.request

import pandas as pd
from modules.data_pipeline import load_data, norm_cat

# Public OSRM demo server (free, no API key). Used only on explicit request.
OSRM_BASE = "http://router.project-osrm.org/route/v1/driving"
OSRM_TIMEOUT = 5  # seconds


EVENT_TIERS = {
    "vip_movement":      {"officers": 60, "barricades": 120, "tow": 4, "k9": True,  "pilots": True},
    "protest":           {"officers": 40, "barricades": 60,  "tow": 1, "reserve": True},
    "public_event":      {"officers": 30, "barricades": 60,  "tow": 2, "crowd": True},
    "procession":        {"officers": 25, "barricades": 35,  "tow": 1, "crowd": True},
    "accident":          {"officers": 6,  "barricades": 6,   "tow": 2, "ambulance": True},
    "construction":      {"officers": 4,  "barricades": 8,   "tow": 1},
    "tree_fall":         {"officers": 5,  "barricades": 3,   "tow": 1},
    "water_logging":     {"officers": 5,  "barricades": 4,   "tow": 1},
    "pot_holes":         {"officers": 3,  "barricades": 2,   "tow": 0},
    "road_conditions":   {"officers": 3,  "barricades": 2,   "tow": 0},
    "debris":            {"officers": 3,  "barricades": 2,   "tow": 1},
    "congestion":        {"officers": 4,  "barricades": 2,   "tow": 0},
    "vehicle_breakdown": {"officers": 2,  "barricades": 0,   "tow": 1},
    "others":            {"officers": 3,  "barricades": 2,   "tow": 0},
}
DEFAULT_TIER = {"officers": 3, "barricades": 2, "tow": 0}

# ── Scaling multipliers ──────────────────────────────────────────────────────────
SEVERITY_SCALE = {"High": 1.0, "Medium": 0.6, "Low": 0.35}
CBD_CORRIDORS  = {"cbd 1", "cbd 2"}
ORR_PREFIX     = "orr"
CORRIDOR_SCALE = {"cbd": 1.30, "orr": 1.15, "standard": 1.00}
PEAK_SCALE     = 1.15
PRIORITY_SCALE = 1.15

# Peak windows (must match data_pipeline.PEAK_HOURS): 4-7 AM, 7-10 PM
PEAK_HOURS_SET = {4, 5, 6, 7, 19, 20, 21, 22}

# Duration → relief-shift multiplier (long events need rotating personnel).
# A standard police shift is ~8h; events spanning multiple shifts need relief.
def duration_multiplier(hours: float) -> tuple:
    if hours >= 8:
        return 1.6, "≥8h (3 shifts) ×1.6"
    if hours >= 4:
        return 1.3, "4–8h (relief shift) ×1.3"
    if hours >= 2:
        return 1.1, "2–4h ×1.1"
    return 1.0, "<2h ×1.0"


def event_touches_peak(start_hour: int, duration_hrs: float) -> bool:
    """True if the event window [start, start+duration) overlaps any peak hour."""
    span = int(max(1, round(duration_hrs)))
    for h in range(start_hour, start_hour + span):
        if (h % 24) in PEAK_HOURS_SET:
            return True
    return False

# ── Vehicle classes for tow type ─────────────────────────────────────────────────
HEAVY_VEH = {"heavy_vehicle", "truck", "bmtc_bus", "ksrtc_bus"}
MED_VEH   = {"lcv", "private_bus"}

# ── Cause-specific special equipment ─────────────────────────────────────────────
SPECIAL_EQUIPMENT = {
    "tree_fall":       ["Tree-cutting crew + log crane"],
    "water_logging":   ["High-capacity de-watering pumps"],
    "pot_holes":       ["Debris loader + asphalt patch kit"],
    "road_conditions": ["Debris loader + asphalt patch kit"],
    "debris":          ["Debris-clearing crew"],
    "vip_movement":    ["K9 sweep units", "Pilot/escort vehicles"],
    "protest":         ["KSRP/CAR reserve platoon", "Water-cannon standby"],
    "public_event":    ["Crowd-control barriers", "Ambulance coordination"],
    "procession":      ["Route marshals", "Crowd-control barriers"],
    "accident":        ["Ambulance coordination"],
}


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

    # ── Core recommendation — event-type tiers + deterministic scaling ──────────

    @staticmethod
    def _corridor_factor(corridor_norm: str) -> tuple:
        if corridor_norm in CBD_CORRIDORS:
            return CORRIDOR_SCALE["cbd"], "CBD ×1.30"
        if corridor_norm.startswith(ORR_PREFIX):
            return CORRIDOR_SCALE["orr"], "ORR ×1.15"
        return CORRIDOR_SCALE["standard"], "standard ×1.00"

    def _tow_class(self, veh_type: str, severity: str, base_tow: int, cause: str) -> str:
        if base_tow <= 0:
            return "None"
        # Large managed events keep heavy recovery fleet on standby regardless of veh_type
        if cause in {"vip_movement", "public_event", "protest", "procession"}:
            return "Heavy-duty recovery fleet (standby)"
        if veh_type in HEAVY_VEH:
            return "Heavy-duty recovery vehicle"
        if veh_type in MED_VEH and severity == "High":
            return "Medium-duty utility tow"
        return "Light flatbed tow truck"

    def recommend(self, event: dict, severity: str = None) -> dict:
        """
        Build a full deployment plan from event-type tiers, scaled by severity,
        corridor density, peak hour and priority. No LLM — fully deterministic
        and traceable. Per-junction figures plus corridor-aggregated totals.
        """
        severity      = severity or "Medium"
        corridor_disp = event.get("corridor") or "Non-corridor"
        corridor_norm = norm_cat(corridor_disp) or "non-corridor"
        cause         = norm_cat(event.get("event_cause")) or "others"
        category      = norm_cat(event.get("event_category")) or ""
        veh_type      = norm_cat(event.get("veh_type")) or "others"
        road_closure  = bool(event.get("requires_road_closure"))
        priority      = event.get("priority", "Low")
        start_hour    = int(event.get("hour", 12))
        duration_hrs  = float(event.get("duration_hrs", 1) or 1)

        # Peak now derived from whether the event WINDOW overlaps a rush hour
        is_peak = event_touches_peak(start_hour, duration_hrs)

        if cause in EVENT_TIERS:
            tier = EVENT_TIERS[cause]
        else:
            if category == "planned_event":
                tier = EVENT_TIERS.get("public_event", DEFAULT_TIER)
            elif category == "infrastructure_hazards":
                tier = EVENT_TIERS.get("water_logging", DEFAULT_TIER)
            elif category == "traffic_incidents":
                tier = EVENT_TIERS.get("congestion", DEFAULT_TIER)
            else:
                tier = EVENT_TIERS.get("others", DEFAULT_TIER)

        # Severity scales the base fully; the situational factors (corridor, peak,
        # priority) only ADD a bounded uplift so large-base events don't balloon.
        sev_f = SEVERITY_SCALE.get(severity, 0.6)
        cor_f, cor_lbl = self._corridor_factor(corridor_norm)
        peak_f = PEAK_SCALE if is_peak else 1.0
        prio_f = PRIORITY_SCALE if priority == "High" else 1.0
        # uplift = combined situational bonus, capped at +40%
        uplift = min(1.40, cor_f * peak_f * prio_f)

        # Duration multiplier — applied SEPARATELY (relief shifts), not capped,
        # because a longer event genuinely needs more total personnel to rotate.
        dur_f, dur_lbl = duration_multiplier(duration_hrs)

        mult = sev_f * uplift * dur_f

        # Per-junction resources
        officers   = max(1, math.ceil(tier["officers"] * mult))
        # barricades are physical infra — they don't rotate, so duration doesn't
        # multiply them (you don't need more barricades for a longer event).
        barricades = max(0, round(tier["barricades"] * sev_f * uplift))
        base_tow   = tier["tow"]
        # closure on a normally tow-less event still needs 1 recovery vehicle
        if base_tow == 0 and road_closure:
            base_tow = 1
        tow_count  = base_tow
        tow_class  = self._tow_class(veh_type, severity, tow_count, cause)

        # Support vehicles (friend's logic)
        patrol_jeeps = max(1, officers // 10) if officers >= 4 else 0
        command_vans = 2 if cause == "vip_movement" else (1 if (severity == "High" and road_closure) else 0)

        # Special equipment by cause
        equipment = list(SPECIAL_EQUIPMENT.get(cause, []))

        officer_breakdown = (
            f"{tier['officers']} base ({cause}) · {severity} ×{sev_f} · "
            f"{cor_lbl} · {'peak ×1.15 · ' if is_peak else ''}"
            f"{'priority ×1.15 · ' if priority=='High' else ''}"
            f"duration {dur_lbl} · ≈ {officers}/junction"
        )
        shift_rotation = duration_hrs >= 4   # event spans multiple police shifts

        # Deployment junctions + corridor-aggregated totals
        junctions = self._corridor_junctions.get(corridor_norm, [])
        n_points = {"High": 3, "Medium": 2, "Low": 1}.get(severity, 1)
        deploy_at = junctions[:n_points] if junctions else ["(no named junction on record — deploy at incident point)"]
        n_deploy = len(deploy_at)

        station = self._corridor_station.get(corridor_norm, "Nearest available station")

        return {
            "severity":            severity,
            # per-junction
            "officers":            officers,
            "barricades":          barricades,
            "tow_vehicles":        tow_count,
            "tow_class":           tow_class,
            "patrol_jeeps":        patrol_jeeps,
            "command_vans":        command_vans,
            "officer_breakdown":   officer_breakdown,
            "special_equipment":   equipment,
            "duration_hrs":        duration_hrs,
            "shift_rotation":      shift_rotation,
            "is_peak":             is_peak,
            # corridor totals (across all deployment junctions)
            "n_deploy_points":     n_deploy,
            "total_officers":      officers * n_deploy,
            "total_barricades":    barricades * n_deploy,
            # locations
            "deploy_at":           deploy_at,
            "primary_junction":    deploy_at[0] if deploy_at else None,
            "owning_station":      station,
            "road_closure":        road_closure,
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
