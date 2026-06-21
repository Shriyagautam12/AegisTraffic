import React, { useState, useEffect, useRef } from 'react';
import L from 'leaflet';

export default function EventSimulator() {
  const CAUSES = [
    "public_event", "procession", "vip_movement", "protest", "construction",
    "accident", "vehicle_breakdown", "tree_fall", "water_logging", "pot_holes", "congestion"
  ];

  const CORRIDORS = [
    "Airport New South Road", "Bannerghatta Road", "Bellary Road 1", "Bellary Road 2",
    "CBD 1", "CBD 2", "Hennur Main Road", "Hosur Road", "IRR(Thanisandra road)",
    "Magadi Road", "Mysore Road", "Non-corridor", "Old Airport Road", "Old Madras Road",
    "ORR East 1", "ORR East 2", "ORR North 1", "ORR North 2", "ORR West 1",
    "Tumkur Road", "Varthur Road", "West of Chord Road"
  ];

  const VEHICLES = [
    "(none)", "auto", "bmtc_bus", "heavy_vehicle", "ksrtc_bus", "lcv",
    "private_bus", "private_car", "taxi", "truck", "others"
  ];

  // Form states
  const [cause, setCause] = useState('vip_movement');
  const [corridor, setCorridor] = useState('Airport New South Road');
  const [veh, setVeh] = useState('(none)');
  const [startDate, setStartDate] = useState(new Date().toISOString().split('T')[0]);
  const [startTime, setStartTime] = useState('18:00');
  const [duration, setDuration] = useState(4.0);
  const [closure, setClosure] = useState(true);

  // Result states
  const [simData, setSimData] = useState(null);
  const [opPlan, setOpPlan] = useState(null);

  // Loading states
  const [simulating, setSimulating] = useState(false);
  const [loadingNarrative, setLoadingNarrative] = useState(false);

  // OSRM map ref
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const mapLayerGroupRef = useRef(null);

  // Form submit handler
  const handleSimulate = (e) => {
    e.preventDefault();
    setSimulating(true);
    setSimData(null);
    setOpPlan(null);

    const payload = {
      event_cause: cause,
      corridor: corridor,
      veh_type: veh,
      start_date: startDate,
      start_time: startTime,
      duration_hrs: parseFloat(duration),
      requires_road_closure: closure
    };

    fetch('/api/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(res => {
        if (!res.ok) throw new Error("Simulation failed");
        return res.json();
      })
      .then(data => {
        setSimData(data);
        setSimulating(false);
      })
      .catch(err => {
        console.error("Simulation error: ", err);
        setSimulating(false);
      });
  };

  // Generate Gemini Operational Narrative
  const handleGenerateNarrative = () => {
    if (!simData) return;
    setLoadingNarrative(true);
    setOpPlan(null);

    const payload = {
      event: simData.event,
      prediction: simData.prediction
    };

    fetch('/api/simulate-narrative', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(res => res.json())
      .then(data => {
        setOpPlan(data);
        setLoadingNarrative(false);
      })
      .catch(err => {
        console.error("Error generating narrative: ", err);
        setLoadingNarrative(false);
      });
  };

  // Setup Leaflet map for OSRM Route Rerouting
  useEffect(() => {
    if (!simData || !simData.diversion_plan || !mapRef.current) return;
    const dplan = simData.diversion_plan;
    if (!dplan.available) return;

    // Get origin & destination coordinates from OSRM
    const hasNormalCoords = dplan.normal_route?.geometry?.coordinates;
    if (!hasNormalCoords || hasNormalCoords.length === 0) return;

    const normalCoords = dplan.normal_route.geometry.coordinates;
    const origin = [normalCoords[0][1], normalCoords[0][0]]; // [lat, lon]
    const dest = [normalCoords[normalCoords.length - 1][1], normalCoords[normalCoords.length - 1][0]];

    const center = [
      (origin[0] + dest[0]) / 2,
      (origin[1] + dest[1]) / 2
    ];

    if (!mapInstanceRef.current) {
      mapInstanceRef.current = L.map(mapRef.current, {
        center: center,
        zoom: 13,
        zoomControl: true,
      });

      L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap &copy; CARTO'
      }).addTo(mapInstanceRef.current);

      mapLayerGroupRef.current = L.featureGroup().addTo(mapInstanceRef.current);
    } else {
      mapLayerGroupRef.current.clearLayers();
      mapInstanceRef.current.setView(center, 13);
    }

    // Direct route (Red Polyline)
    if (dplan.normal_route && dplan.normal_route.geometry) {
      const coords = dplan.normal_route.geometry.coordinates.map(c => [c[1], c[0]]);
      L.polyline(coords, {
        color: '#ef4444',
        weight: 5,
        opacity: 0.85,
        dashArray: '2, 5' // dotted to show blocked
      }).addTo(mapLayerGroupRef.current)
        .bindPopup(`<b>Direct Route:</b> ${dplan.normal_route.duration_mins} mins, ${dplan.normal_route.distance_km} km`);
    }

    // Diverted route (Green Polyline)
    if (dplan.diverted_route && dplan.diverted_route.geometry) {
      const coords = dplan.diverted_route.geometry.coordinates.map(c => [c[1], c[0]]);
      L.polyline(coords, {
        color: '#2f9e57',
        weight: 5,
        opacity: 0.9,
      }).addTo(mapLayerGroupRef.current)
        .bindPopup(`<b>Diverted Route:</b> ${dplan.diverted_route.duration_mins} mins, ${dplan.diverted_route.distance_km} km`);
    }

    // Origin marker (Blue)
    L.circleMarker(origin, {
      radius: 8,
      color: '#ffffff', // white border
      weight: 2,
      fillColor: '#3b82f6', // Blue
      fillOpacity: 1.0,
    }).bindPopup('<b>Incident Origin Point</b>').addTo(mapLayerGroupRef.current);

    // Destination marker (Orange)
    L.circleMarker(dest, {
      radius: 8,
      color: '#ffffff', // white border
      weight: 2,
      fillColor: '#e8932e', // Orange
      fillOpacity: 1.0,
    }).bindPopup('<b>Bypass Destination Point</b>').addTo(mapLayerGroupRef.current);

    // Fit map bounds
    const bounds = L.latLngBounds([origin, dest]);
    mapInstanceRef.current.fitBounds(bounds, { padding: [40, 40] });

  }, [simData]);

  // Deriving ranks from total force
  const deriveRanks = (n) => {
    const dcp = n >= 80 ? 1 : 0;
    const acp = n >= 60 ? Math.max(0, Math.round(n / 120)) : 0;
    const pi = n >= 8 ? Math.max(1, Math.round(n / 25)) : (n >= 4 ? 1 : 0);
    const psi = n >= 12 ? Math.max(0, Math.round(n / 12)) : 0;
    const hg = n >= 40 ? Math.round(n * 0.20) : 0;
    const constables = Math.max(0, n - dcp - acp - pi - psi - hg);
    return [
      { label: 'DCP', val: dcp, color: '#fca5a5' },
      { label: 'ACP', val: acp, color: '#fcd34d' },
      { label: 'PI', val: pi, color: '#60a5fa' },
      { label: 'PSI/ASI', val: psi, color: '#a78bfa' },
      { label: 'Constables', val: constables, color: '#5eead4' },
      { label: 'Home Guards', val: hg, color: '#93c5fd' }
    ];
  };

  return (
    <div className="page-container">
      {/* Banner */}
      <div className="page-title-banner">
        <div className="page-title-icon">🔮</div>
        <div className="page-title-info">
          <h1 className="page-title">Event Impact Simulator</h1>
          <span className="page-subtitle">Describe an event → get a full AI-drafted command plan, grounded in our models.</span>
        </div>
      </div>

      {/* Input controls form */}
      <div className="glass-card">
        <div className="card-title card-title-border">Describe the Event</div>
        <form onSubmit={handleSimulate} className="simulator-form">
          <div className="input-grid-3">
            <div className="form-group">
              <label className="form-label">Event cause</label>
              <select className="form-input" value={cause} onChange={(e) => setCause(e.target.value)}>
                {CAUSES.map(c => <option key={c} value={c}>{c.replace('_', ' ')}</option>)}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Corridor</label>
              <select className="form-input" value={corridor} onChange={(e) => setCorridor(e.target.value)}>
                {CORRIDORS.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Vehicle type (if any)</label>
              <select className="form-input" value={veh} onChange={(e) => setVeh(e.target.value)}>
                {VEHICLES.map(v => <option key={v} value={v}>{v}</option>)}
              </select>
            </div>
          </div>

          <div className="input-grid-4">
            <div className="form-group">
              <label className="form-label">Event Date</label>
              <input type="date" className="form-input" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>

            <div className="form-group">
              <label className="form-label">Start Time</label>
              <input type="time" className="form-input" value={startTime} onChange={(e) => setStartTime(e.target.value)} />
            </div>

            <div className="form-group">
              <label className="form-label">Duration: {duration} hrs</label>
              <input
                type="range"
                min="0.5"
                max="12.0"
                step="0.5"
                className="form-input"
                value={duration}
                onChange={(e) => setDuration(e.target.value)}
                style={{ padding: '5px 0' }}
              />
            </div>

            <div className="checkbox-form-wrap">
              <label className="form-checkbox-label">
                <input
                  type="checkbox"
                  checked={closure}
                  onChange={(e) => setClosure(e.target.checked)}
                  style={{ width: '18px', height: '18px', accentColor: 'var(--color-amber)' }}
                />
                <span>Road closure required</span>
              </label>
            </div>
          </div>

          <button type="submit" className="submit-btn" disabled={simulating}>
            {simulating ? (
              <>
                <span className="spinner" style={{ width: '18px', height: '18px', borderLeftColor: '#fff' }}></span>
                <span>Calculating Predictions...</span>
              </>
            ) : (
              <span>⚡ Generate Command Plan</span>
            )}
          </button>
        </form>
      </div>

      {/* Render Simulation results */}
      {simData && (
        <div className="flex-column-gap-10" style={{ gap: '30px' }}>

          {/* Grounded Prediction strip */}
          <div className="glass-card">
            <div className="card-title card-title-border">Grounded Prediction (AegisTraffic ML)</div>

            <div className="metrics-strip">
              <div className="metric-item">
                <span className="metric-lbl">Severity</span>
                <span className={`sev-badge ${simData.prediction.severity.toLowerCase()}`} style={{ marginTop: '8px' }}>
                  {simData.prediction.severity}
                </span>
                <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                  {Math.round(simData.prediction.confidence * 100)}% confidence
                </span>
              </div>

              <div className="metric-item">
                <span className="metric-lbl">Est. Clearance</span>
                <span className="metric-val" style={{ color: 'var(--color-blue)' }}>
                  {Math.round(simData.prediction.duration_mins)}m
                </span>
                {simData.prediction.correction_factor !== 1.0 && (
                  <span style={{ fontSize: '0.74rem', color: 'var(--color-blue)', fontWeight: 600 }}>
                    Learned correction: ×{simData.prediction.correction_factor.toFixed(2)}
                  </span>
                )}
              </div>

              <div className="metric-item">
                <span className="metric-lbl">Critical Event?</span>
                <span className={`metric-val ${simData.prediction.is_critical ? 'text-red' : ''}`} style={{ color: simData.prediction.is_critical ? 'var(--color-red)' : 'var(--color-green)' }}>
                  {simData.prediction.is_critical ? 'YES' : 'NO'}
                </span>
              </div>

              <div className="metric-item">
                <span className="metric-lbl">Owning Station</span>
                <span className="metric-val" style={{ color: 'var(--color-purple)', fontSize: '1.4rem', paddingTop: '10px' }}>
                  {simData.resource_plan.owning_station}
                </span>
              </div>
            </div>

            <div style={{ marginTop: '18px', fontSize: '0.9rem', fontWeight: 600 }}>
              <span>Why: </span>
              {simData.prediction.top_reasons.map((r) => (
                <span key={r.feature} className="why-chip">
                  {r.feature} {r.direction === 'increases' ? '▲' : '▼'}
                </span>
              ))}
            </div>
          </div>

          {/* Personnel Deployment */}
          <div className="glass-card">
            <div className="card-title card-title-border">👮 Personnel Deployment</div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '15px' }}>
              {deriveRanks(simData.resource_plan.total_officers).map(rank => (
                <div key={rank.label} className="metric-item" style={{ alignItems: 'center', padding: '15px' }}>
                  <span className="metric-val" style={{ color: rank.color, fontSize: '1.8rem' }}>{rank.val}</span>
                  <span className="metric-lbl" style={{ fontSize: '0.7rem' }}>{rank.label}</span>
                </div>
              ))}
            </div>

            <div style={{ marginTop: '14px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <span style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--text-secondary)' }}>
                Total deployment force: <strong style={{ color: '#111' }}>{simData.resource_plan.total_officers}</strong> personnel ({simData.resource_plan.officers} per junction × {simData.resource_plan.n_deploy_points} locations).
              </span>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                Time window: {simData.event.start_datetime_display} · {simData.event.hour}:00–{Math.round((simData.event.hour + simData.resource_plan.duration_hrs) % 24)}:00 ({simData.resource_plan.duration_hrs}h)
                {simData.resource_plan.shift_rotation && " · spans multiple shifts — relief rotation factored in"}
              </span>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontStyle: 'italic', marginTop: '2px' }}>
                {simData.resource_plan.officer_breakdown}
              </span>
            </div>
          </div>

          {/* Logistics & Special Units */}
          <div className="glass-card">
            <div className="card-title card-title-border">🚧 Logistics & Special Units</div>

            <div className="metrics-strip">
              <div className="metric-item" style={{ padding: '14px', alignItems: 'center' }}>
                <span className="metric-val" style={{ color: 'var(--color-gold-start)' }}>{simData.resource_plan.total_barricades}</span>
                <span className="metric-lbl">Barricades</span>
              </div>
              <div className="metric-item" style={{ padding: '14px', alignItems: 'center' }}>
                <span className="metric-val" style={{ color: 'var(--color-red)' }}>{simData.resource_plan.tow_vehicles}</span>
                <span className="metric-lbl">Tow Vehicles</span>
              </div>
              <div className="metric-item" style={{ padding: '14px', alignItems: 'center' }}>
                <span className="metric-val" style={{ color: 'var(--color-blue)' }}>{simData.resource_plan.patrol_jeeps}</span>
                <span className="metric-lbl">Patrol Jeeps</span>
              </div>
              <div className="metric-item" style={{ padding: '14px', alignItems: 'center' }}>
                <span className="metric-val" style={{ color: 'var(--color-purple)' }}>{simData.resource_plan.command_vans}</span>
                <span className="metric-lbl">Command Vans</span>
              </div>
            </div>

            <div style={{ marginTop: '14px', fontSize: '0.82rem', color: 'var(--text-secondary)', fontWeight: 600 }}>
              <span>Tow class: <strong>{simData.resource_plan.tow_class}</strong></span>
              {simData.resource_plan.special_equipment.length > 0 && (
                <span> · Equipment: <strong>{simData.resource_plan.special_equipment.join(', ')}</strong></span>
              )}
            </div>
          </div>

          {/* AI Narrative plan trigger */}
          <div className="glass-card">
            <div className="card-title card-title-border">🧭 Diversion & Operational Narrative</div>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '15px' }}>
              Numbers above are AegisTraffic's deterministic rules. Click below to generate AI-drafted diversion plans, timelines, and advisories.
            </p>
            <button className="submit-btn" onClick={handleGenerateNarrative} disabled={loadingNarrative} style={{ background: '#475569', boxShadow: 'none' }}>
              {loadingNarrative ? (
                <>
                  <span className="spinner" style={{ width: '18px', height: '18px', borderLeftColor: '#fff' }}></span>
                  <span>Drafting diversion plans...</span>
                </>
              ) : (
                <span>🧭 Show Diversion Routes & AI Plan</span>
              )}
            </button>

            {/* Narrative outputs */}
            {opPlan && opPlan.available && (
              <div className="flex-column-gap-10" style={{ marginTop: '24px', gap: '20px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                  {/* Diversion Legs */}
                  <div className="glass-card" style={{ padding: '18px' }}>
                    <div className="card-title card-title-border" style={{ fontSize: '0.9rem' }}>🧭 Diversion Routes</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {opPlan.plan.diversion_legs && opPlan.plan.diversion_legs.map((leg, index) => (
                        <div key={index} className="similar-event-card" style={{ padding: '10px', background: '#fafafa' }}>
                          <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)', fontWeight: 700 }}>
                            {leg.for_whom || 'Commuters'}
                          </span>
                          <span style={{ fontSize: '0.86rem', fontWeight: 600 }}>
                            <strong>{leg.from}</strong> → <span style={{ color: 'var(--color-blue)' }}>{leg.via}</span> → <strong>{leg.to}</strong>
                          </span>
                        </div>
                      ))}
                      {(!opPlan.plan.diversion_legs || opPlan.plan.diversion_legs.length === 0) && (
                        <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>No diversion required.</span>
                      )}
                      {opPlan.plan.hgv_ban && (
                        <div style={{ fontSize: '0.82rem', marginTop: '5px' }}>
                          🚛 <strong>HGV restriction:</strong> {opPlan.plan.hgv_ban}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Precedent details */}
                  <div className="glass-card" style={{ padding: '18px' }}>
                    <div className="card-title card-title-border" style={{ fontSize: '0.9rem' }}>📜 What History Shows</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {simData.precedents.typical_closure_mins !== null ? (
                        <span style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                          Typically clears in <span style={{ color: 'var(--color-blue)' }}>~{Math.round(simData.precedents.typical_closure_mins)} min</span>
                          {simData.precedents.low_confidence && ' ⚠️ limited data'} · {simData.precedents.high_severity_count}/5 precedent cases were High.
                        </span>
                      ) : (
                        <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>No historical precedents found.</span>
                      )}

                      {simData.precedents.similar_events && simData.precedents.similar_events.slice(0, 3).map((s) => (
                        <div key={s.id} className="similar-event-card" style={{ padding: '10px', background: '#fafafa' }}>
                          <div className="similar-event-header">
                            <span className="similar-event-date">{s.date} · {s.day}</span>
                            <span className={`sev-badge ${s.severity.toLowerCase()}`} style={{ fontSize: '0.7rem', padding: '2px 8px' }}>
                              {s.severity}
                            </span>
                          </div>
                          <span className="similar-event-sub">
                            {s.event_cause} on {s.corridor} · {s.closure_mins ? `${Math.round(s.closure_mins)} min` : 'n/a'}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Timeline */}
                <div className="glass-card" style={{ padding: '18px' }}>
                  <div className="card-title card-title-border" style={{ fontSize: '0.9rem' }}>⏱️ Operational Timeline</div>
                  <div style={{ display: 'grid', gridTemplateColumns: `repeat(${opPlan.plan.timeline ? opPlan.plan.timeline.length : 1}, 1fr)`, gap: '15px', marginTop: '10px' }}>
                    {opPlan.plan.timeline && opPlan.plan.timeline.map((ph, idx) => (
                      <div key={idx} className="metric-item" style={{ minHeight: '130px', padding: '12px' }}>
                        <span className="timeline-phase" style={{ color: 'var(--color-blue)', fontWeight: 800 }}>{ph.phase}</span>
                        <span className="timeline-label" style={{ fontSize: '0.86rem', marginTop: '2px' }}>{ph.label}</span>
                        <span className="timeline-action" style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '6px', lineHeight: '1.3' }}>
                          {ph.actions}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Command & Advisory */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                  <div className="glass-card" style={{ padding: '18px' }}>
                    <div className="card-title card-title-border" style={{ fontSize: '0.9rem' }}>🎖️ Command & Control</div>
                    <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>{opPlan.plan.command}</p>
                  </div>
                  <div className="glass-card" style={{ padding: '18px', borderColor: 'var(--color-amber)' }}>
                    <div className="card-title card-title-border" style={{ fontSize: '0.9rem' }}>📢 Public Advisory (VMS)</div>
                    <div style={{ padding: '12px', background: '#1e293b', borderRadius: '8px', color: '#f59e0b', fontFamily: 'monospace', fontSize: '0.85rem' }}>
                      {opPlan.plan.vms_advisory}
                    </div>
                  </div>
                </div>

                <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                  ⚠️ Diversion routes & timeline are AI-drafted from operational norms — verify against current ground conditions.
                </span>
              </div>
            )}

            {opPlan && !opPlan.available && (
              <div style={{ marginTop: '20px', padding: '12px', background: '#fffbeb', color: '#b45309', border: '1px solid #fef3c7', borderRadius: '10px', fontSize: '0.88rem' }}>
                ⚠️ AI Narrative unavailable: <strong>{opPlan.reason}</strong>. Resource numbers above remain fully valid.
              </div>
            )}
          </div>

          {/* Severity Probabilities */}
          <div className="glass-card">
            <div className="card-title card-title-border">Severity Probabilities</div>

            <div className="flex-column-gap-10" style={{ gap: '12px' }}>
              {['Low', 'Medium', 'High'].map(classLabel => {
                const prob = simData.prediction.probabilities[classLabel] || 0;
                const percent = Math.round(prob * 100);
                const color = classLabel === 'High' ? 'var(--color-red)' : classLabel === 'Medium' ? 'var(--color-amber)' : 'var(--color-green)';
                return (
                  <div key={classLabel} style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                    <span style={{ width: '60px', fontSize: '0.85rem', fontWeight: 700 }}>{classLabel}</span>
                    <div style={{ flexGrow: 1, height: '16px', background: '#f3f4f6', borderRadius: '8px', overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${percent}%`, backgroundColor: color, borderRadius: '8px', transition: 'width 0.5s ease-in-out' }}></div>
                    </div>
                    <span style={{ width: '40px', fontSize: '0.85rem', fontWeight: 700, textAlign: 'right' }}>{percent}%</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Optional live OSRM diversion map */}
          {closure && simData.diversion_plan && simData.diversion_plan.available && (
            <div className="glass-card flex-column-gap-10">
              <div className="card-title card-title-border">🗺️ Live Diversion Route (OSRM)</div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '10px' }}>
                <div className="metric-item">
                  <span className="metric-lbl">Direct (Blocked)</span>
                  <span className="metric-val" style={{ color: 'var(--color-red)' }}>
                    {simData.diversion_plan.normal_route.duration_mins}m
                  </span>
                  <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                    {simData.diversion_plan.normal_route.distance_km} km
                  </span>
                </div>
                <div className="metric-item">
                  <span className="metric-lbl">Via {simData.diversion_plan.alternate_corridor || 'Alternate'}</span>
                  <span className="metric-val" style={{ color: 'var(--color-green)' }}>
                    {simData.diversion_plan.diverted_route?.duration_mins || 'n/a'}m
                  </span>
                  <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                    {simData.diversion_plan.diverted_route?.distance_km || 'n/a'} km
                  </span>
                </div>
              </div>

              {simData.diversion_plan.time_penalty_mins !== null && (
                <div style={{ fontSize: '0.88rem', fontWeight: 700, margin: '5px 0' }}>
                  Time penalty: <span style={{ color: 'var(--color-red)' }}>+{simData.diversion_plan.time_penalty_mins} min</span>
                  <span style={{ fontWeight: 500, color: 'var(--text-muted)' }}> (bypass coordinates centered on alternate corridor)</span>
                </div>
              )}

              <div ref={mapRef} style={{ height: '380px', borderRadius: '14px', border: '1px solid var(--border-color)', position: 'relative' }}></div>
            </div>
          )}

        </div>
      )}
    </div>
  );
}
