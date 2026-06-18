"""
Module 5 — Geo-Spatial Risk Visualization Engine
Builds Folium map layers for the dashboard. Pure rendering: consumes data from
Module 1 (intelligence) and Module 4 (diversion geometry); contains no analysis.

Returns folium.Map objects that Streamlit renders via streamlit-folium.
"""

import folium
from folium.plugins import HeatMap, MarkerCluster

# Bengaluru map center + default zoom
BLR_CENTER = (12.9716, 77.5946)
DEFAULT_ZOOM = 11

# Severity → colour / weight
SEVERITY_COLOR = {"High": "red", "Medium": "orange", "Low": "green"}
SEVERITY_WEIGHT = {"High": 1.0, "Medium": 0.6, "Low": 0.3}

# Chronic chokepoint threshold (median closure mins) for pin colouring
CHRONIC_MEDIAN_MINS = 200


def _base_map(center=BLR_CENTER, zoom=DEFAULT_ZOOM) -> folium.Map:
    return folium.Map(
        location=list(center),
        zoom_start=zoom,
        tiles="cartodbpositron",   # clean light basemap; roads/landmarks visible
        control_scale=True,
    )


# ── Layer 1: Incident heatmap ───────────────────────────────────────────────────

def incident_heatmap(incidents_df, center=BLR_CENTER, zoom=DEFAULT_ZOOM) -> folium.Map:
    """City-wide incident density, weighted by severity."""
    m = _base_map(center, zoom)
    heat_data = [
        [row["latitude"], row["longitude"], SEVERITY_WEIGHT.get(row["severity"], 0.3)]
        for _, row in incidents_df.iterrows()
        if row["latitude"] and row["longitude"]
    ]
    HeatMap(
        heat_data,
        radius=11, blur=15, max_zoom=13,
        gradient={0.2: "blue", 0.45: "lime", 0.65: "orange", 1.0: "red"},
        name="Incident density",
    ).add_to(m)
    folium.LayerControl().add_to(m)
    return m


# ── Layer 2: Junction risk pins ─────────────────────────────────────────────────

def junction_risk_map(junction_df, center=BLR_CENTER, zoom=DEFAULT_ZOOM) -> folium.Map:
    """
    Top junctions as colour-coded circles:
      red    = chronic (median closure > threshold)
      orange = high frequency (>= 30 incidents)
      yellow = moderate
    """
    m = _base_map(center, zoom)
    for _, r in junction_df.iterrows():
        if not (r.get("lat") and r.get("lon")):
            continue
        median = r.get("median_closure_mins")
        count  = r.get("incident_count", 0)
        if median is not None and median >= CHRONIC_MEDIAN_MINS:
            color, tier = "red", "Chronic chokepoint"
        elif count >= 30:
            color, tier = "orange", "High frequency"
        else:
            color, tier = "#d4a017", "Moderate"

        median_txt = f"{median:.0f} min" if median is not None else "n/a"
        popup = folium.Popup(
            f"<b>{r['junction']}</b><br>"
            f"Tier: {tier}<br>"
            f"Incidents: {count}<br>"
            f"Median closure: {median_txt}<br>"
            f"Hotspot score: {r.get('hotspot_score', 0):.3f}",
            max_width=260,
        )
        folium.CircleMarker(
            location=[r["lat"], r["lon"]],
            radius=5 + min(count, 60) / 10.0,   # size scales with frequency
            color=color, fill=True, fill_color=color, fill_opacity=0.7,
            weight=1, popup=popup, tooltip=r["junction"],
        ).add_to(m)
    return m


# ── Layer 3: Single event pin (for the simulator) ───────────────────────────────

def event_pin_map(lat, lon, severity, label="Predicted event",
                  duration_mins=None, zoom=14) -> folium.Map:
    """Drop a marker for a single simulated/predicted event."""
    m = _base_map(center=(lat, lon), zoom=zoom)
    color = SEVERITY_COLOR.get(severity, "blue")
    dur_txt = f"<br>Est. closure: {duration_mins:.0f} min" if duration_mins else ""
    folium.Marker(
        location=[lat, lon],
        popup=folium.Popup(f"<b>{label}</b><br>Severity: {severity}{dur_txt}", max_width=240),
        tooltip=f"{label} ({severity})",
        icon=folium.Icon(color=color, icon="exclamation-sign"),
    ).add_to(m)
    folium.Circle(
        location=[lat, lon], radius=400, color=color,
        fill=True, fill_opacity=0.12, weight=1,
    ).add_to(m)
    return m


# ── Layer 4: Diversion route overlay ────────────────────────────────────────────

def diversion_map(origin, dest, diversion_plan, zoom=13) -> folium.Map:
    """
    Draw normal route (red solid) vs diverted route (green dashed) from a
    Module 4 diversion_plan() result. Falls back to plain markers if routing
    geometry is unavailable.
    """
    center = ((origin[0] + dest[0]) / 2, (origin[1] + dest[1]) / 2)
    m = _base_map(center=center, zoom=zoom)

    folium.Marker(origin, tooltip="Origin",
                  icon=folium.Icon(color="blue", icon="play")).add_to(m)
    folium.Marker(dest, tooltip="Destination",
                  icon=folium.Icon(color="darkblue", icon="flag")).add_to(m)

    def _draw(route, color, dash, label):
        if not route or "geometry" not in route:
            return
        # GeoJSON is [lon, lat]; folium wants [lat, lon]
        coords = [[c[1], c[0]] for c in route["geometry"]["coordinates"]]
        folium.PolyLine(
            coords, color=color, weight=5, opacity=0.8,
            dash_array=dash,
            tooltip=f"{label}: {route.get('duration_mins','?')} min, "
                    f"{route.get('distance_km','?')} km",
        ).add_to(m)

    if diversion_plan.get("available"):
        _draw(diversion_plan.get("normal_route"), "red", None, "Normal (blocked) route")
        _draw(diversion_plan.get("diverted_route"), "green", "10", "Diversion")
    return m


# ── Combined operational map (heatmap + junction pins) ──────────────────────────

def combined_risk_map(incidents_df, junction_df,
                      center=BLR_CENTER, zoom=DEFAULT_ZOOM) -> folium.Map:
    """Heatmap + junction pins in one map with layer toggles — the Page 1 hero map."""
    m = _base_map(center, zoom)

    # Heat layer
    heat_data = [
        [row["latitude"], row["longitude"], SEVERITY_WEIGHT.get(row["severity"], 0.3)]
        for _, row in incidents_df.iterrows()
        if row["latitude"] and row["longitude"]
    ]
    heat_fg = folium.FeatureGroup(name="Incident heatmap", show=True)
    HeatMap(heat_data, radius=11, blur=15,
            gradient={0.2: "blue", 0.45: "lime", 0.65: "orange", 1.0: "red"}
            ).add_to(heat_fg)
    heat_fg.add_to(m)

    # Junction pins layer
    pin_fg = folium.FeatureGroup(name="Junction risk pins", show=True)
    for _, r in junction_df.iterrows():
        if not (r.get("lat") and r.get("lon")):
            continue
        median = r.get("median_closure_mins")
        count  = r.get("incident_count", 0)
        if median is not None and median >= CHRONIC_MEDIAN_MINS:
            color = "red"
        elif count >= 30:
            color = "orange"
        else:
            color = "#d4a017"
        median_txt = f"{median:.0f} min" if median is not None else "n/a"
        folium.CircleMarker(
            location=[r["lat"], r["lon"]],
            radius=5 + min(count, 60) / 10.0,
            color=color, fill=True, fill_color=color, fill_opacity=0.7, weight=1,
            tooltip=r["junction"],
            popup=folium.Popup(
                f"<b>{r['junction']}</b><br>Incidents: {count}<br>"
                f"Median closure: {median_txt}", max_width=240),
        ).add_to(pin_fg)
    pin_fg.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    return m
