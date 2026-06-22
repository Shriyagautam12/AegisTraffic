import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet.heat';

export default function RiskIntelligence({ overviewData }) {
  const [incidents, setIncidents] = useState([]);
  const [junctions, setJunctions] = useState([]);
  const [chronic, setChronic] = useState([]);
  const [activity, setActivity] = useState(null);

  // UI controls
  const [layerType, setLayerType] = useState('Heatmap + Pins'); // 'Heatmap + Pins', 'Heatmap only', 'Junction pins only'
  const [showChronic, setShowChronic] = useState(true);
  const [loading, setLoading] = useState(true);

  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const layersGroupRef = useRef(null);

  // Fetch Incidents & Map data
  useEffect(() => {
    fetch('/api/incidents')
      .then(res => res.json())
      .then(data => {
        setIncidents(data.incidents || []);
        setJunctions(data.junctions || []);
        setChronic(data.chronic || []);
        setLoading(false);
      })
      .catch(err => {
        console.error("Error fetching map data: ", err);
        setLoading(false);
      });

    // Fetch default activity level
    fetch('/api/activity-level')
      .then(res => res.json())
      .then(data => {
        setActivity(data);
      })
      .catch(err => console.error("Error fetching activity level: ", err));
  }, []);

  // Initialize Leaflet Map
  useEffect(() => {
    if (!mapRef.current) return;

    if (!mapInstanceRef.current) {
      mapInstanceRef.current = L.map(mapRef.current, {
        center: [12.9716, 77.5946],
        zoom: 11.5,
        zoomControl: true,
        scrollWheelZoom: true,
      });

      L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap &copy; CARTO'
      }).addTo(mapInstanceRef.current);

      layersGroupRef.current = L.featureGroup().addTo(mapInstanceRef.current);
    }

    return () => {
      // Clean up map instance on unmount
      if (mapInstanceRef.current) {
        // mapInstanceRef.current.remove();
        // mapInstanceRef.current = null;
      }
    };
  }, []);

  // Update Map Layers when data or settings change
  useEffect(() => {
    if (!mapInstanceRef.current || !layersGroupRef.current) return;

    // Clear previous markers/shapes
    layersGroupRef.current.clearLayers();

    const formatHHMM = (minutes) => {
      if (!minutes) return '00:00';
      const totalHrs = Math.floor(minutes / 60);
      const mins = Math.floor(minutes % 60);
      const pad = (num) => String(num).padStart(2, '0');
      
      if (totalHrs >= 24) {
        const days = Math.floor(totalHrs / 24);
        return `${days}d`;
      }
      return `${pad(totalHrs)}:${pad(mins)}`;
    };

    // 1. Draw Heatmap (leaflet.heat canvas)
    if (layerType === 'Heatmap + Pins' || layerType === 'Heatmap only') {
      const heatPoints = incidents
        .filter(inc => inc.latitude && inc.longitude)
        .map(inc => {
          let weight = 0.3;
          if (inc.severity === 'High') weight = 1.0;
          else if (inc.severity === 'Medium') weight = 0.6;
          return [inc.latitude, inc.longitude, weight];
        });

      if (heatPoints.length > 0) {
        L.heatLayer(heatPoints, {
          radius: 30,
          blur: 24,
          maxZoom: 13,
          minOpacity: 0.35,
          gradient: { 0.2: '#1A9E6B', 0.45: '#FCD34D', 0.7: '#F59E0B', 1.0: '#E5484D' }
        }).addTo(layersGroupRef.current);
      }
    }

    // 2. Draw Junction Risk Pins
    if (layerType === 'Heatmap + Pins' || layerType === 'Junction pins only') {
      junctions.forEach(j => {
        if (!j.lat || !j.lon) return;

        let color = '#ca8a04'; // Moderate (yellow/gold)
        let tierName = 'Moderate';

        if (j.median_closure_mins >= 200) {
          color = '#d6453b'; // Red for chronic
          tierName = 'Chronic chokepoint';
        } else if (j.incident_count >= 30) {
          color = '#e8932e'; // Orange for high freq
          tierName = 'High frequency';
        }

        const medianTxt = j.median_closure_mins ? formatHHMM(j.median_closure_mins) : 'n/a';

        L.circleMarker([j.lat, j.lon], {
          radius: 5,
          color: '#ffffff', // white border
          weight: 2,
          fillColor: color,
          fillOpacity: 1.0,
          pane: 'markerPane',
        }).bindPopup(`
          <div>
            <h3 style="margin:0 0 5px 0; font-weight:700; color:#111; font-size:14px;">${j.junction}</h3>
            <p style="margin:0; font-size:12px; color:#555; line-height:1.4;">
              <strong>Tier:</strong> ${tierName}<br/>
              <strong>Incidents:</strong> ${j.incident_count}<br/>
              <strong>Median Closure:</strong> ${medianTxt}<br/>
              <strong>Hotspot Score:</strong> ${j.hotspot_score ? j.hotspot_score.toFixed(3) : '0.000'}
            </p>
          </div>
        `).addTo(layersGroupRef.current);
      });
    }

    // 3. Draw Chronic Pins
    if (showChronic && chronic.length > 0) {
      chronic.forEach(c => {
        if (!c.lat || !c.lon) return;

        const medianTxt = c.median_closure_mins ? formatHHMM(c.median_closure_mins) : 'n/a';

        const icon = L.divIcon({
          className: "",
          html: '<div class="aeg-pin"><span class="ring"></span><span class="core"></span></div>',
          iconSize: [26, 26],
          iconAnchor: [13, 13]
        });

        L.marker([c.lat, c.lon], { icon }).bindPopup(`
          <div>
            <h3 style="margin:0 0 5px 0; font-weight:700; color:#d6453b; font-size:14px;">⚠️ CHRONIC: ${c.junction}</h3>
            <p style="margin:0; font-size:12px; color:#555; line-height:1.4;">
              <strong>Chronic Chokepoint</strong><br/>
              <strong>Incidents:</strong> ${c.incident_count}<br/>
              <strong>Median Clearance:</strong> ${medianTxt}
            </p>
          </div>
        `).addTo(layersGroupRef.current);
      });
    }

  }, [incidents, junctions, chronic, layerType, showChronic]);

  // Activity Gauge SVG Constants
  const pct = activity ? activity.pct_of_peak : 0.0;
  const level = activity ? activity.level : 'MODERATE';
  const timeDisplay = activity ? activity.time_display : 'Fri 23:46';

  const radius = 70;
  const stroke = 8;
  const normalizedRadius = radius - stroke * 2;
  const circumference = normalizedRadius * 2 * Math.PI;
  const strokeDashoffset = circumference - (pct * circumference);

  // Gauge color based on level
  const gaugeColor =
    level === 'HIGH' ? '#e74c3c' :
      level === 'MODERATE' ? '#e8932e' : '#2f9e57';

  // Format table minutes
  const formatHHMMSS = (minutes) => {
    if (minutes === null || minutes === undefined) return "—";
    const totalSecs = Math.round(minutes * 60);
    const days = Math.floor(totalSecs / 86400);
    const hrs = Math.floor((totalSecs % 86400) / 3600);
    const mins = Math.floor((totalSecs % 3600) / 60);
    const secs = totalSecs % 60;

    const pad = (num) => String(num).padStart(2, '0');
    if (days > 0) {
      return `${days}d ${pad(hrs)}h ${pad(mins)}m ${pad(secs)}s`;
    }
    return `${pad(hrs)}h ${pad(mins)}m ${pad(secs)}s`;
  };

  // Top Risk Corridors from API data
  const corridors = overviewData?.top_corridors || [];
  const maxRiskIndex = corridors.length > 0 ? Math.max(...corridors.map(c => c.corridor_risk_index)) : 1;

  // Donut slices for Causes Chart
  const causes = overviewData?.cause_distribution || [];
  const totalCauseCount = causes.reduce((acc, curr) => acc + curr.count, 0);

  // Slices generation logic for SVG Donut
  let accumulatedPercent = 0;
  const causeColors = [
    '#5eead4', '#60a5fa', '#a78bfa', '#fca5f5',
    '#fcd34d', '#fca5a5', '#93c5fd', '#3b82f6'
  ];

  const donutRadius = 80;
  const donutCircumference = 2 * Math.PI * donutRadius;

  const donutSlices = causes.map((c, i) => {
    const percent = totalCauseCount > 0 ? (c.count / totalCauseCount) * 100 : 0;
    const sliceLength = (percent * donutCircumference) / 100;
    const startOffset = (accumulatedPercent / 100) * donutCircumference;
    
    accumulatedPercent += percent;

    // The gap in dashArray must be exactly the rest of the circumference so the pattern length is 1 circumference.
    const dashArray = `${sliceLength} ${Math.max(0, donutCircumference - sliceLength)}`;
    
    // We shift the start of the dash backward by startOffset
    const dashOffset = donutCircumference - startOffset;

    return {
      cause: c.cause,
      count: c.count,
      percent: percent,
      color: causeColors[i % causeColors.length],
      dashArray,
      dashOffset
    };
  });

  return (
    <div className="page-container">
      {/* Title */}
      <div className="page-title-banner">
        <div className="page-title-info">
          <h1 className="page-title">Risk Intelligence</h1>
          <span className="page-subtitle">Where Bengaluru chokes — and when.</span>
        </div>
      </div>

      {/* Main Grid: Map & Controls */}
      <div className="risk-grid">
        <div className="glass-card flex-column-gap-10">
          <div className="card-title card-title-border">Bengaluru Incident Map</div>

          <div className="map-container">
            {loading && (
              <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', zIndex: 1000, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' }}>
                <span className="spinner"></span>
                <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#555' }}>Loading incident data...</span>
              </div>
            )}
            <div ref={mapRef} className="map-element"></div>
          </div>

          <div className="map-caption">
            <span style={{ display: 'inline-block', width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#ef4444' }}></span>
            <span>Red pins = chronic chokepoints (median clearance &gt; 200 min).</span>
          </div>
        </div>

        {/* Right column: Activity Gauge + Map layer selection */}
        <div className="flex-column-gap-10" style={{ gap: '20px', height: '100%' }}>
          {/* Activity Gauge */}
          <div className="glass-card">
            <div className="card-title card-title-border">Activity Level Now</div>
            <div className="gauge-outer">
              <div className="gauge-svg-wrap">
                <svg width="150" height="150" style={{ transform: 'rotate(-90deg)', filter: 'drop-shadow(0 4px 6px rgba(0,0,0,0.05))' }}>
                  <circle
                    stroke="#f1f3f5"
                    fill="transparent"
                    strokeWidth={stroke}
                    r={normalizedRadius}
                    cx="75"
                    cy="75"
                  />
                  <circle
                    stroke={gaugeColor}
                    fill="transparent"
                    strokeWidth={stroke}
                    strokeDasharray={circumference}
                    strokeDashoffset={strokeDashoffset}
                    strokeLinecap="round"
                    r={normalizedRadius}
                    cx="75"
                    cy="75"
                    style={{ transition: 'stroke-dashoffset 1s ease-out' }}
                  />
                </svg>
                <div className="gauge-inner-content">
                  <div className="gauge-pct-val" style={{ color: gaugeColor }}>
                    {Math.round(pct * 100)}<span className="gauge-pct-sign">%</span>
                  </div>
                  <span className="gauge-lbl-level" style={{ color: gaugeColor }}>{level}</span>
                </div>
              </div>
              <span className="gauge-lbl-when">{timeDisplay}</span>
              <span className="gauge-lbl-sub">City-Wide Activity</span>
            </div>
          </div>

          {/* Map Layer Option Selection */}
          <div className="glass-card" style={{ flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
            <div className="card-title card-title-border">Map Layer</div>
            <div className="control-options" style={{ flexGrow: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
              <div className="radio-group">
                {['Heatmap + Pins', 'Heatmap only', 'Junction pins only'].map((opt) => (
                  <label
                    key={opt}
                    className={`radio-label ${layerType === opt ? 'active' : ''}`}
                  >
                    <input
                      type="radio"
                      name="map-layer"
                      checked={layerType === opt}
                      onChange={() => setLayerType(opt)}
                      style={{ accentColor: 'var(--color-amber)' }}
                    />
                    <span>{opt}</span>
                  </label>
                ))}
              </div>

              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={showChronic}
                  onChange={(e) => setShowChronic(e.target.checked)}
                  style={{ accentColor: 'var(--color-red)' }}
                />
                <span>⚠️ Show chronic chokepoints</span>
              </label>
            </div>
          </div>
        </div>
      </div>

      {/* Visualizations Grid */}
      <div className="charts-grid">
        {/* Top Risk Corridors */}
        <div className="glass-card">
          <div className="card-title card-title-border">Top Risk Corridors</div>
          <div className="bar-chart-container">
            {corridors.map((c) => {
              const pct = (c.corridor_risk_index / maxRiskIndex) * 100;
              return (
                <div key={c.corridor} className="chart-bar-row">
                  <div className="chart-bar-header">
                    <span className="chart-bar-name">{c.corridor}</span>
                    <span>{(c.corridor_risk_index * 10).toFixed(1)} / 10.0</span>
                  </div>
                  <div className="chart-bar-bg">
                    <div className="chart-bar-fill" style={{ width: `${pct}%` }}></div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Incident Causes Donut */}
        <div className="glass-card">
          <div className="card-title card-title-border">Incident Causes</div>
          <div className="donut-container">
            <div className="donut-svg-wrap">
              <svg width="200" height="200" style={{ transform: 'rotate(-90deg)' }}>
                {donutSlices.map((slice, i) => (
                  <circle
                    key={slice.cause}
                    stroke={slice.color}
                    fill="transparent"
                    strokeWidth="20"
                    strokeDasharray={slice.dashArray}
                    strokeDashoffset={slice.dashOffset}
                    r="80"
                    cx="100"
                    cy="100"
                  />
                ))}
              </svg>
            </div>

            <div className="donut-legend">
              {donutSlices.map((slice) => (
                <div key={slice.cause} className="legend-item">
                  <div className="legend-item-left">
                    <span className="legend-color-dot" style={{ backgroundColor: slice.color }}></span>
                    <span className="legend-item-name">{slice.cause.replace('_', ' ')}</span>
                  </div>
                  <span>{slice.percent.toFixed(0)}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Chronic Chokepoints Table */}
      <div className="glass-card">
        <div className="card-title card-title-border">⚠️ Chronic Chokepoints (median clearance &gt; 200 min)</div>
        <div className="table-wrapper">
          <table className="custom-table">
            <thead>
              <tr>
                <th>Junction</th>
                <th>Incidents</th>
                <th>Median Clearance</th>
              </tr>
            </thead>
            <tbody>
              {chronic.slice(0, 12).map((chr) => (
                <tr key={chr.junction}>
                  <td className="table-cell-bold">{chr.junction}</td>
                  <td>{chr.incident_count}</td>
                  <td><span className="clearance-badge">{formatHHMMSS(chr.median_closure_mins)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
