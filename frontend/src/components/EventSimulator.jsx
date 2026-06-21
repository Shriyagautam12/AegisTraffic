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

  const CORRIDOR_OPTIONS = [
    ...CORRIDORS.map(c => ({ value: c, label: c })),
    { value: 'others', label: 'Others (specify)' }
  ];

  const VEHICLES = [
    "(none)", "auto", "bmtc_bus", "heavy_vehicle", "ksrtc_bus", "lcv",
    "private_bus", "private_car", "taxi", "truck", "others"
  ];

  const VEHICLE_OPTIONS = [
    { value: '(none)', label: 'None' },
    { value: 'auto', label: 'Auto' },
    { value: 'bmtc_bus', label: 'BMTC BUS' },
    { value: 'heavy_vehicle', label: 'Heavy Vehicle' },
    { value: 'ksrtc_bus', label: 'KSRTC BUS' },
    { value: 'lcv', label: 'LCV' },
    { value: 'private_bus', label: 'Private Bus' },
    { value: 'private_car', label: 'Private Car' },
    { value: 'taxi', label: 'Taxi' },
    { value: 'truck', label: 'Truck' },
    { value: 'others', label: 'Others' }
  ];

  const now = new Date();
  const currentHours = String(now.getHours()).padStart(2, '0');
  const currentMinutes = String(now.getMinutes()).padStart(2, '0');
  const currentTime = `${currentHours}:${currentMinutes}`;

  // Form states
  const [category, setCategory] = useState('');
  const [subcategory, setSubcategory] = useState('');
  const [customCause, setCustomCause] = useState('');
  const [subcategorySearchQuery, setSubcategorySearchQuery] = useState('');
  const [categoryDropdownOpen, setCategoryDropdownOpen] = useState(false);
  const [subcategoryDropdownOpen, setSubcategoryDropdownOpen] = useState(false);
  const categoryDropdownRef = useRef(null);
  const subcategoryDropdownRef = useRef(null);

  const [corridor, setCorridor] = useState('');
  const [customCorridor, setCustomCorridor] = useState('');
  const [corridorSearchQuery, setCorridorSearchQuery] = useState('');
  const [corridorDropdownOpen, setCorridorDropdownOpen] = useState(false);
  const corridorDropdownRef = useRef(null);
  const [veh, setVeh] = useState('');
  const [startDate, setStartDate] = useState(now.toISOString().split('T')[0]);
  const [startTime, setStartTime] = useState(currentTime);
  const [duration, setDuration] = useState('');
  const [closure, setClosure] = useState(false);

  // Calendar Picker state
  const [calendarOpen, setCalendarOpen] = useState(false);
  const calendarRef = useRef(null);
  
  const parseDate = (dStr) => {
    if (!dStr) return new Date();
    const parts = dStr.split('-');
    return new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
  };
  
  const parsedStart = parseDate(now.toISOString().split('T')[0]);
  const [calendarMonth, setCalendarMonth] = useState(parsedStart.getMonth());
  const [calendarYear, setCalendarYear] = useState(parsedStart.getFullYear());

  // Time Picker state
  const [timeOpen, setTimeOpen] = useState(false);
  const timeRef = useRef(null);

  // Result states
  const [simData, setSimData] = useState(null);
  const [showDiversion, setShowDiversion] = useState(false);

  // ── Human-in-the-loop feedback states ───────────────────────────────────────
  const [fbOfficers, setFbOfficers] = useState('');
  const [fbBarricades, setFbBarricades] = useState('');
  const [fbPatrolJeeps, setFbPatrolJeeps] = useState('');
  const [fbTowVehicles, setFbTowVehicles] = useState('');
  const [fbCommandVans, setFbCommandVans] = useState('');
  const [fbSeverity, setFbSeverity] = useState('Medium');
  const [fbDuration, setFbDuration] = useState('');
  const [fbStatus, setFbStatus] = useState(null); // null | 'submitting' | 'success' | 'error'
  const [fbMsg, setFbMsg] = useState('');
  // Tracks the original suggested values so we know if the user has edited anything
  const fbOriginal = useRef({});

  // Pre-populate feedback form whenever a simulation result arrives
  useEffect(() => {
    if (simData) {
      const rp = simData.resource_plan;
      const seed = {
        officers:    rp.total_officers   ?? '',
        barricades:  rp.total_barricades ?? '',
        patrolJeeps: rp.patrol_jeeps     ?? '',
        towVehicles: rp.tow_vehicles     ?? '',
        commandVans: rp.command_vans     ?? '',
        severity:    simData.prediction.severity       ?? 'Medium',
        duration:    Math.round(simData.prediction.duration_mins) ?? '',
      };
      fbOriginal.current = seed;
      setFbOfficers(seed.officers);
      setFbBarricades(seed.barricades);
      setFbPatrolJeeps(seed.patrolJeeps);
      setFbTowVehicles(seed.towVehicles);
      setFbCommandVans(seed.commandVans);
      setFbSeverity(seed.severity);
      setFbDuration(seed.duration);
      setFbStatus(null);
      setFbMsg('');
    }
  }, [simData]);

  // True as soon as any value differs from the original suggestion
  const isEdited = simData && (
    String(fbOfficers)    !== String(fbOriginal.current.officers)    ||
    String(fbBarricades)  !== String(fbOriginal.current.barricades)  ||
    String(fbPatrolJeeps) !== String(fbOriginal.current.patrolJeeps) ||
    String(fbTowVehicles) !== String(fbOriginal.current.towVehicles) ||
    String(fbCommandVans) !== String(fbOriginal.current.commandVans) ||
    fbSeverity            !== fbOriginal.current.severity            ||
    String(fbDuration)    !== String(fbOriginal.current.duration)
  );

  const handleFeedback = (approved) => {
    if (!simData) return;
    setFbStatus('submitting');
    setFbMsg('');
    const payload = {
      prediction_id: simData.prediction_id,
      actual_severity: fbSeverity,
      actual_duration: parseFloat(fbDuration) || Math.round(simData.prediction.duration_mins),
      actual_officers: parseInt(fbOfficers) || null,
      actual_barricades: parseInt(fbBarricades) || null,
      actual_patrol_jeeps: parseInt(fbPatrolJeeps) || null,
      actual_tow_vehicles: parseInt(fbTowVehicles) || null,
      actual_command_vans: parseInt(fbCommandVans) || null,
    };
    fetch('/api/learning/outcome', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then(res => res.json())
      .then(data => {
        setFbStatus('success');
        setFbMsg(approved
          ? '✅ Suggested plan approved and saved to learning system.'
          : '✅ Adjusted deployment saved. The system will learn from this feedback.');
      })
      .catch(() => {
        setFbStatus('error');
        setFbMsg('❌ Failed to save feedback. Please try again.');
      });
  };

  // Loading states
  const [simulating, setSimulating] = useState(false);

  // OSRM map ref
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const mapLayerGroupRef = useRef(null);

  // Form submit handler
  const handleSimulate = (e) => {
    e.preventDefault();
    if (!category) {
      alert("Please select an Event Category.");
      return;
    }
    if (!subcategory) {
      alert("Please select an Event Cause (Subcategory).");
      return;
    }
    if (subcategory === 'others' && !customCause.trim()) {
      alert("Please specify the event cause details.");
      return;
    }
    if (!corridor) {
      alert("Please select a Corridor.");
      return;
    }
    if (corridor === 'others' && !customCorridor.trim()) {
      alert("Please specify the corridor name.");
      return;
    }
    if (!duration) {
      alert("Please enter a Duration.");
      return;
    }
    setSimulating(true);
    setSimData(null);
    setShowDiversion(false);

    const resolvedCause = subcategory === 'others' && customCause.trim()
      ? customCause.trim().toLowerCase().replace(/\s+/g, '_')
      : subcategory;

    const resolvedCorridor = corridor === 'others' && customCorridor.trim()
      ? customCorridor.trim()
      : corridor;

    const payload = {
      event_category: category,
      event_subcategory: subcategory,
      event_cause: resolvedCause,
      corridor: resolvedCorridor,
      veh_type: veh === '' ? null : (veh === '(none)' ? null : veh),
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

  const CATEGORIES = [
    { value: 'planned_event', label: 'Planned Event' },
    { value: 'infrastructure_hazards', label: 'Infrastructure & Hazards' },
    { value: 'traffic_incidents', label: 'Traffic Incidents' }
  ];

  const SUBCATEGORIES = {
    planned_event: [
      { value: 'public_event', label: 'Public Event' },
      { value: 'procession', label: 'Procession' },
      { value: 'vip_movement', label: 'VIP Movement' },
      { value: 'protest', label: 'Protest' },
      { value: 'construction', label: 'Construction' },
      { value: 'others', label: 'Others (specify)' }
    ],
    infrastructure_hazards: [
      { value: 'tree_fall', label: 'Tree Fall' },
      { value: 'water_logging', label: 'Water Logging' },
      { value: 'pot_holes', label: 'Pot Holes' },
      { value: 'others', label: 'Others (specify)' }
    ],
    traffic_incidents: [
      { value: 'accident', label: 'Accident' },
      { value: 'vehicle_breakdown', label: 'Vehicle Breakdown' },
      { value: 'congestion', label: 'Congestion' },
      { value: 'others', label: 'Others (specify)' }
    ]
  };

  // Click outside to close custom dropdown, calendar, and time pickers
  useEffect(() => {
    function handleClickOutside(event) {
      if (categoryDropdownRef.current && !categoryDropdownRef.current.contains(event.target)) {
        setCategoryDropdownOpen(false);
      }
      if (subcategoryDropdownRef.current && !subcategoryDropdownRef.current.contains(event.target)) {
        setSubcategoryDropdownOpen(false);
      }
      if (corridorDropdownRef.current && !corridorDropdownRef.current.contains(event.target)) {
        setCorridorDropdownOpen(false);
      }
      if (calendarRef.current && !calendarRef.current.contains(event.target)) {
        setCalendarOpen(false);
      }
      if (timeRef.current && !timeRef.current.contains(event.target)) {
        setTimeOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const getDaysInMonth = (y, m) => new Date(y, m + 1, 0).getDate();
  const getFirstDayOfMonth = (y, m) => new Date(y, m, 1).getDay();

  const isSameDay = (y, m, d, compareStr) => {
    if (!compareStr) return false;
    const parts = compareStr.split('-');
    return parseInt(parts[0], 10) === y && (parseInt(parts[1], 10) - 1) === m && parseInt(parts[2], 10) === d;
  };

  const formatDisplayDate = (dStr) => {
    if (!dStr) return "Pick a date";
    const d = parseDate(dStr);
    return d.toLocaleDateString('default', { month: 'long', day: 'numeric', year: 'numeric' });
  };

  const prevMonth = () => {
    if (calendarMonth === 0) {
      setCalendarMonth(11);
      setCalendarYear(calendarYear - 1);
    } else {
      setCalendarMonth(calendarMonth - 1);
    }
  };

  const nextMonth = () => {
    if (calendarMonth === 11) {
      setCalendarMonth(0);
      setCalendarYear(calendarYear + 1);
    } else {
      setCalendarMonth(calendarMonth + 1);
    }
  };

  const selectDate = (y, m, d) => {
    const formatted = `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    setStartDate(formatted);
    setCalendarOpen(false);
  };

  const selectHour = (hrStr) => {
    const currentMin = startTime.split(':')[1] || '00';
    setStartTime(`${hrStr}:${currentMin}`);
  };

  const selectMinute = (minStr) => {
    const currentHr = startTime.split(':')[0] || '12';
    setStartTime(`${currentHr}:${minStr}`);
    setTimeOpen(false);
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
    if (showDiversion && dplan.diverted_route && dplan.diverted_route.geometry) {
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

  }, [simData, showDiversion]);

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
          <div className="input-grid-4">
            <div className="form-group" ref={categoryDropdownRef} style={{ position: 'relative' }}>
              <label className="form-label">Event Category</label>
              <div 
                className="form-input" 
                onClick={() => setCategoryDropdownOpen(!categoryDropdownOpen)}
                style={{ 
                  cursor: 'pointer', 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'center',
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '12px',
                  padding: '12px 14px'
                }}
              >
                <span style={{ color: category ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                  {CATEGORIES.find(opt => opt.value === category)?.label || "Select Category..."}
                </span>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginLeft: '10px' }}>{categoryDropdownOpen ? '▲' : '▼'}</span>
              </div>

              {categoryDropdownOpen && (
                <div style={{
                  position: 'absolute',
                  top: '100%',
                  left: 0,
                  right: 0,
                  background: 'white',
                  border: '1px solid var(--border-color)',
                  borderRadius: '12px',
                  boxShadow: '0 8px 30px rgba(0,0,0,0.08)',
                  zIndex: 1000,
                  marginTop: '6px',
                  maxHeight: '260px',
                  display: 'flex',
                  flexDirection: 'column',
                  overflow: 'hidden'
                }}>
                  {/* Category Options */}
                  <div style={{ overflowY: 'auto', flexGrow: 1 }}>
                    {CATEGORIES.map(opt => (
                      <div
                        key={opt.value}
                        onClick={() => {
                          setCategory(opt.value);
                          setSubcategory(''); // Reset subcategory on category change
                          setCustomCause(''); // Reset custom specify box
                          setCategoryDropdownOpen(false);
                        }}
                        style={{
                          padding: '10px 14px',
                          cursor: 'pointer',
                          fontSize: '0.92rem',
                          background: category === opt.value ? '#f0fdf4' : 'transparent',
                          color: category === opt.value ? 'var(--color-green)' : 'var(--text-primary)',
                          fontWeight: category === opt.value ? '700' : '500',
                          transition: 'background 0.15s'
                        }}
                        onMouseOver={(e) => {
                          if (category !== opt.value) e.currentTarget.style.background = '#f5f5f5';
                        }}
                        onMouseOut={(e) => {
                          if (category !== opt.value) e.currentTarget.style.background = 'transparent';
                        }}
                      >
                        {opt.label}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="form-group" ref={subcategoryDropdownRef} style={{ position: 'relative' }}>
              <label className="form-label">Event Cause (Subcategory)</label>
              <div 
                className="form-input" 
                onClick={() => {
                  if (category) {
                    setSubcategoryDropdownOpen(!subcategoryDropdownOpen);
                  }
                }}
                style={{ 
                  cursor: category ? 'pointer' : 'not-allowed', 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'center',
                  background: category ? 'var(--bg-card)' : '#f9f9f9',
                  border: '1px solid var(--border-color)',
                  borderRadius: '12px',
                  padding: '12px 14px',
                  opacity: category ? 1 : 0.6
                }}
              >
                <span style={{ color: subcategory ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                  {category 
                    ? (SUBCATEGORIES[category]?.find(opt => opt.value === subcategory)?.label || "Select Cause...")
                    : "Select Category First"
                  }
                </span>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginLeft: '10px' }}>{subcategoryDropdownOpen ? '▲' : '▼'}</span>
              </div>

              {category && subcategoryDropdownOpen && (
                <div style={{
                  position: 'absolute',
                  top: '100%',
                  left: 0,
                  right: 0,
                  background: 'white',
                  border: '1px solid var(--border-color)',
                  borderRadius: '12px',
                  boxShadow: '0 8px 30px rgba(0,0,0,0.08)',
                  zIndex: 1000,
                  marginTop: '6px',
                  maxHeight: '260px',
                  display: 'flex',
                  flexDirection: 'column',
                  overflow: 'hidden'
                }}>
                  {/* Search input */}
                  <div style={{ padding: '8px', borderBottom: '1px solid #f0f0f0' }}>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Search cause..."
                      value={subcategorySearchQuery}
                      onChange={(e) => setSubcategorySearchQuery(e.target.value)}
                      onClick={(e) => e.stopPropagation()} // Prevent close on search click
                      style={{
                        padding: '8px 12px',
                        fontSize: '0.88rem',
                        borderRadius: '8px',
                        border: '1px solid #e0e0e0',
                        width: '100%',
                        boxSizing: 'border-box'
                      }}
                    />
                  </div>
                  {/* Options */}
                  <div style={{ overflowY: 'auto', flexGrow: 1 }}>
                    {(SUBCATEGORIES[category] || []).filter(opt => 
                      opt.label.toLowerCase().includes(subcategorySearchQuery.toLowerCase())
                    ).map(opt => (
                      <div
                        key={opt.value}
                        onClick={() => {
                          setSubcategory(opt.value);
                          setSubcategoryDropdownOpen(false);
                          setSubcategorySearchQuery('');
                        }}
                        style={{
                          padding: '10px 14px',
                          cursor: 'pointer',
                          fontSize: '0.92rem',
                          background: subcategory === opt.value ? '#f0fdf4' : 'transparent',
                          color: subcategory === opt.value ? 'var(--color-green)' : 'var(--text-primary)',
                          fontWeight: subcategory === opt.value ? '700' : '500',
                          transition: 'background 0.15s'
                        }}
                        onMouseOver={(e) => {
                          if (subcategory !== opt.value) e.currentTarget.style.background = '#f5f5f5';
                        }}
                        onMouseOut={(e) => {
                          if (subcategory !== opt.value) e.currentTarget.style.background = 'transparent';
                        }}
                      >
                        {opt.label}
                      </div>
                    ))}
                    {(SUBCATEGORIES[category] || []).filter(opt => 
                      opt.label.toLowerCase().includes(subcategorySearchQuery.toLowerCase())
                    ).length === 0 && (
                      <div style={{ padding: '12px 14px', fontSize: '0.88rem', color: 'var(--text-muted)', fontStyle: 'italic', textAlign: 'center' }}>
                        No match found
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            <div className="form-group" ref={corridorDropdownRef} style={{ position: 'relative' }}>
              <label className="form-label">Corridor</label>
              <div 
                className="form-input" 
                onClick={() => setCorridorDropdownOpen(!corridorDropdownOpen)}
                style={{ 
                  cursor: 'pointer', 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'center',
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '12px',
                  padding: '12px 14px'
                }}
              >
                <span style={{ color: corridor ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                  {CORRIDOR_OPTIONS.find(opt => opt.value === corridor)?.label || "Select Corridor..."}
                </span>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginLeft: '10px' }}>{corridorDropdownOpen ? '▲' : '▼'}</span>
              </div>

              {corridorDropdownOpen && (
                <div style={{
                  position: 'absolute',
                  top: '100%',
                  left: 0,
                  right: 0,
                  background: 'white',
                  border: '1px solid var(--border-color)',
                  borderRadius: '12px',
                  boxShadow: '0 8px 30px rgba(0,0,0,0.08)',
                  zIndex: 1000,
                  marginTop: '6px',
                  maxHeight: '260px',
                  display: 'flex',
                  flexDirection: 'column',
                  overflow: 'hidden'
                }}>
                  {/* Search input */}
                  <div style={{ padding: '8px', borderBottom: '1px solid #f0f0f0' }}>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Search corridor..."
                      value={corridorSearchQuery}
                      onChange={(e) => setCorridorSearchQuery(e.target.value)}
                      onClick={(e) => e.stopPropagation()} // Prevent close on search click
                      style={{
                        padding: '8px 12px',
                        fontSize: '0.88rem',
                        borderRadius: '8px',
                        border: '1px solid #e0e0e0',
                        width: '100%',
                        boxSizing: 'border-box'
                      }}
                    />
                  </div>
                  {/* Options */}
                  <div style={{ overflowY: 'auto', flexGrow: 1 }}>
                    {CORRIDOR_OPTIONS.filter(opt => 
                      opt.label.toLowerCase().includes(corridorSearchQuery.toLowerCase())
                    ).map(opt => (
                      <div
                        key={opt.value}
                        onClick={() => {
                          setCorridor(opt.value);
                          setCorridorDropdownOpen(false);
                          setCorridorSearchQuery('');
                        }}
                        style={{
                          padding: '10px 14px',
                          cursor: 'pointer',
                          fontSize: '0.92rem',
                          background: corridor === opt.value ? '#f0fdf4' : 'transparent',
                          color: corridor === opt.value ? 'var(--color-green)' : 'var(--text-primary)',
                          fontWeight: corridor === opt.value ? '700' : '500',
                          transition: 'background 0.15s'
                        }}
                        onMouseOver={(e) => {
                          if (corridor !== opt.value) e.currentTarget.style.background = '#f5f5f5';
                        }}
                        onMouseOut={(e) => {
                          if (corridor !== opt.value) e.currentTarget.style.background = 'transparent';
                        }}
                      >
                        {opt.label}
                      </div>
                    ))}
                    {CORRIDOR_OPTIONS.filter(opt => 
                      opt.label.toLowerCase().includes(corridorSearchQuery.toLowerCase())
                    ).length === 0 && (
                      <div style={{ padding: '12px 14px', fontSize: '0.88rem', color: 'var(--text-muted)', fontStyle: 'italic', textAlign: 'center' }}>
                        No match found
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            <div className="form-group">
              <label className="form-label">Vehicle type (if any)</label>
              <select className="form-input" value={veh} onChange={(e) => setVeh(e.target.value)} required style={{ color: veh ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                <option value="" disabled hidden>Select Vehicle Type...</option>
                {VEHICLE_OPTIONS.map(opt => <option key={opt.value} value={opt.value} style={{ color: 'var(--text-primary)' }}>{opt.label}</option>)}
              </select>
            </div>
          </div>

          {/* Dynamic specify details inputs rendered on their own row to prevent select box squeeze */}
          {(subcategory === 'others' || corridor === 'others') && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
              {subcategory === 'others' ? (
                <div className="form-group">
                  <label className="form-label">Specify Event Cause Details</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="Specify event cause details..."
                    value={customCause}
                    onChange={(e) => setCustomCause(e.target.value)}
                    style={{
                      borderColor: 'var(--color-amber)',
                      boxShadow: '0 0 0 1px var(--color-amber)'
                    }}
                    required
                  />
                </div>
              ) : <div />}
              {corridor === 'others' ? (
                <div className="form-group">
                  <label className="form-label">Specify Corridor Details</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="Specify corridor details..."
                    value={customCorridor}
                    onChange={(e) => setCustomCorridor(e.target.value)}
                    style={{
                      borderColor: 'var(--color-amber)',
                      boxShadow: '0 0 0 1px var(--color-amber)'
                    }}
                    required
                  />
                </div>
              ) : <div />}
            </div>
          )}

          <div className="input-grid-4">
            <div className="form-group" ref={calendarRef} style={{ position: 'relative' }}>
              <label className="form-label">Event Date</label>
              <button
                type="button"
                className="form-input"
                onClick={() => setCalendarOpen(!calendarOpen)}
                style={{
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '12px',
                  padding: '12px 14px',
                  textAlign: 'left',
                  width: '100%',
                  fontWeight: '500',
                  color: 'var(--text-primary)'
                }}
              >
                <span style={{ fontSize: '1rem' }}>📅</span>
                <span>{formatDisplayDate(startDate)}</span>
              </button>

              {calendarOpen && (
                <div style={{
                  position: 'absolute',
                  top: '100%',
                  left: 0,
                  background: 'white',
                  border: '1px solid #e4e4e7',
                  borderRadius: '12px',
                  boxShadow: '0 10px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.1)',
                  padding: '16px',
                  zIndex: 1000,
                  marginTop: '6px',
                  width: '260px'
                }}>
                  {/* Calendar Header */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                    <button type="button" onClick={prevMonth} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.9rem', color: '#71717a' }}>◀</button>
                    <span style={{ fontWeight: '600', fontSize: '0.88rem', color: '#18181b' }}>
                      {new Date(calendarYear, calendarMonth).toLocaleString('default', { month: 'long', year: 'numeric' })}
                    </span>
                    <button type="button" onClick={nextMonth} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.9rem', color: '#71717a' }}>▶</button>
                  </div>
                  {/* Days of Week */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '4px', textAlign: 'center', marginBottom: '8px' }}>
                    {['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map(d => (
                      <span key={d} style={{ fontSize: '0.75rem', fontWeight: '500', color: '#71717a' }}>{d}</span>
                    ))}
                  </div>
                  {/* Days Grid */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '4px' }}>
                    {Array.from({ length: getFirstDayOfMonth(calendarYear, calendarMonth) }).map((_, idx) => (
                      <div key={`empty-${idx}`} />
                    ))}
                    {Array.from({ length: getDaysInMonth(calendarYear, calendarMonth) }).map((_, idx) => {
                      const day = idx + 1;
                      const isSelected = isSameDay(calendarYear, calendarMonth, day, startDate);
                      return (
                        <button
                          key={day}
                          type="button"
                          onClick={() => selectDate(calendarYear, calendarMonth, day)}
                          style={{
                            width: '30px',
                            height: '30px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            borderRadius: '50%',
                            border: 'none',
                            fontSize: '0.8rem',
                            fontWeight: isSelected ? '600' : '400',
                            cursor: 'pointer',
                            background: isSelected ? '#18181b' : 'transparent',
                            color: isSelected ? 'white' : '#18181b',
                            transition: 'background 0.2s'
                          }}
                          onMouseOver={(e) => {
                            if (!isSelected) e.currentTarget.style.background = '#f4f4f5';
                          }}
                          onMouseOut={(e) => {
                            if (!isSelected) e.currentTarget.style.background = 'transparent';
                          }}
                        >
                          {day}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

            <div className="form-group" ref={timeRef} style={{ position: 'relative' }}>
              <label className="form-label">Start Time</label>
              <button
                type="button"
                className="form-input"
                onClick={() => setTimeOpen(!timeOpen)}
                style={{
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '12px',
                  padding: '12px 14px',
                  textAlign: 'left',
                  width: '100%',
                  fontWeight: '500',
                  color: 'var(--text-primary)'
                }}
              >
                <span style={{ fontSize: '1rem' }}>🕒</span>
                <span>{startTime || "Select time"}</span>
              </button>

              {timeOpen && (
                <div style={{
                  position: 'absolute',
                  top: '100%',
                  left: 0,
                  background: 'white',
                  border: '1px solid #e4e4e7',
                  borderRadius: '12px',
                  boxShadow: '0 10px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.1)',
                  padding: '8px',
                  zIndex: 1000,
                  marginTop: '6px',
                  width: '140px',
                  height: '200px',
                  display: 'flex',
                  gap: '4px'
                }}>
                  {/* Hours column */}
                  <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
                    <div style={{ fontSize: '0.7rem', fontWeight: 'bold', color: '#71717a', textAlign: 'center', paddingBottom: '4px', borderBottom: '1px solid #f4f4f5' }}>Hr</div>
                    {Array.from({ length: 24 }).map((_, hr) => {
                      const hrStr = String(hr).padStart(2, '0');
                      const currentHr = startTime.split(':')[0];
                      const isSelected = currentHr === hrStr;
                      return (
                        <button
                          key={hr}
                          type="button"
                          onClick={() => selectHour(hrStr)}
                          style={{
                            background: isSelected ? '#18181b' : 'transparent',
                            color: isSelected ? 'white' : '#18181b',
                            border: 'none',
                            borderRadius: '6px',
                            padding: '6px 0',
                            fontSize: '0.8rem',
                            fontWeight: isSelected ? '600' : '400',
                            cursor: 'pointer',
                            margin: '2px 0'
                          }}
                        >
                          {hrStr}
                        </button>
                      );
                    })}
                  </div>
                  {/* Minutes column */}
                  <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
                    <div style={{ fontSize: '0.7rem', fontWeight: 'bold', color: '#71717a', textAlign: 'center', paddingBottom: '4px', borderBottom: '1px solid #f4f4f5' }}>Min</div>
                    {Array.from({ length: 12 }).map((_, minIdx) => {
                      const minVal = minIdx * 5;
                      const minStr = String(minVal).padStart(2, '0');
                      const currentMin = startTime.split(':')[1];
                      const isSelected = currentMin === minStr;
                      return (
                        <button
                          key={minVal}
                          type="button"
                          onClick={() => selectMinute(minStr)}
                          style={{
                            background: isSelected ? '#18181b' : 'transparent',
                            color: isSelected ? 'white' : '#18181b',
                            border: 'none',
                            borderRadius: '6px',
                            padding: '6px 0',
                            fontSize: '0.8rem',
                            fontWeight: isSelected ? '600' : '400',
                            cursor: 'pointer',
                            margin: '2px 0'
                          }}
                        >
                          {minStr}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

            <div className="form-group">
              <label className="form-label">Duration (hrs)</label>
              <input
                type="number"
                min="0.5"
                max="24.0"
                step="0.5"
                placeholder="Enter duration..."
                className="form-input"
                value={duration}
                onChange={(e) => setDuration(e.target.value)}
                required
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


          {/* ── Operational Deployment Feedback ─────────────────────────────── */}
          <div className="glass-card" style={{ borderTop: '3px solid var(--color-purple)' }}>
            <div className="card-title card-title-border" style={{ borderColor: 'var(--color-purple)' }}>
              🔁 Operational Deployment Feedback
            </div>
            <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', marginBottom: '20px', lineHeight: 1.5 }}>
              Review the suggested deployment plan below. You can <strong>approve</strong> it as-is, or adjust any values to reflect what was actually deployed — the system will learn from every submission.
            </p>

            {/* Resource Inputs */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '16px', marginBottom: '20px' }}>
              {[
                { label: '👮 Officers', value: fbOfficers, setter: setFbOfficers, color: 'var(--color-blue)', predicted: simData?.resource_plan?.total_officers },
                { label: '🚧 Barricades', value: fbBarricades, setter: setFbBarricades, color: 'var(--color-gold-start)', predicted: simData?.resource_plan?.total_barricades },
                { label: '🚔 Patrol Jeeps', value: fbPatrolJeeps, setter: setFbPatrolJeeps, color: 'var(--color-teal)', predicted: simData?.resource_plan?.patrol_jeeps },
                { label: '🚛 Tow Vehicles', value: fbTowVehicles, setter: setFbTowVehicles, color: 'var(--color-red)', predicted: simData?.resource_plan?.tow_vehicles },
                { label: '📡 Command Vans', value: fbCommandVans, setter: setFbCommandVans, color: 'var(--color-purple)', predicted: simData?.resource_plan?.command_vans },
              ].map(({ label, value, setter, color, predicted }) => {
                const diff = parseInt(value) - predicted;
                const hasDiff = !isNaN(diff) && diff !== 0;
                return (
                  <div key={label} style={{
                    background: 'var(--bg-surface)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '14px',
                    padding: '16px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px',
                  }}>
                    <span style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-secondary)' }}>{label}</span>
                    <input
                      type="number"
                      min="0"
                      className="form-input"
                      value={value}
                      onChange={e => setter(e.target.value)}
                      style={{ fontSize: '1.1rem', fontWeight: 700, color, textAlign: 'center', padding: '8px', borderRadius: '8px' }}
                    />
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textAlign: 'center' }}>
                      Suggested: <strong style={{ color }}>{predicted}</strong>
                      {hasDiff && (
                        <span style={{
                          marginLeft: '6px',
                          padding: '1px 6px',
                          borderRadius: '10px',
                          background: diff > 0 ? '#fee2e2' : '#e0f2fe',
                          color: diff > 0 ? '#dc2626' : '#0369a1',
                          fontWeight: 700,
                        }}>
                          {diff > 0 ? `+${diff}` : diff}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Severity & Duration */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '22px' }}>
              <div className="form-group">
                <label className="form-label">Actual Severity</label>
                <select className="form-input" value={fbSeverity} onChange={e => setFbSeverity(e.target.value)}>
                  <option value="High">High</option>
                  <option value="Medium">Medium</option>
                  <option value="Low">Low</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Actual Clearance Duration (min)</label>
                <input type="number" min="1" className="form-input" value={fbDuration} onChange={e => setFbDuration(e.target.value)} />
              </div>
            </div>

            {/* Action Buttons */}
            <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap', alignItems: 'center' }}>

              {/* Approve — active only when nothing has been edited */}
              <button
                onClick={() => handleFeedback(true)}
                disabled={isEdited || fbStatus === 'submitting' || fbStatus === 'success'}
                title={isEdited ? 'You have edited values — use "Record Custom Deployment" instead' : 'Approve the suggested plan as-is'}
                style={{
                  background: isEdited
                    ? '#d1fae5'
                    : 'linear-gradient(135deg, #10b981, #059669)',
                  color: isEdited ? '#6b7280' : 'white',
                  border: isEdited ? '1.5px dashed #6ee7b7' : 'none',
                  borderRadius: '12px',
                  padding: '12px 24px',
                  fontSize: '0.92rem',
                  fontWeight: 700,
                  cursor: isEdited || fbStatus === 'submitting' || fbStatus === 'success' ? 'not-allowed' : 'pointer',
                  opacity: fbStatus === 'submitting' || fbStatus === 'success' ? 0.6 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  boxShadow: isEdited ? 'none' : '0 4px 12px rgba(16,185,129,0.25)',
                  transition: 'all 0.2s ease',
                }}
                onMouseOver={e => { if (!isEdited && fbStatus !== 'success') e.currentTarget.style.transform = 'translateY(-2px)'; }}
                onMouseOut={e => { e.currentTarget.style.transform = 'translateY(0)'; }}
              >
                <span>👍 Approve Suggested Plan</span>
              </button>

              {/* Record Custom — active only after an edit */}
              <button
                onClick={() => handleFeedback(false)}
                disabled={!isEdited || fbStatus === 'submitting' || fbStatus === 'success'}
                title={!isEdited ? 'Edit any value above to enable this button' : 'Save your custom deployment'}
                style={{
                  background: isEdited
                    ? 'linear-gradient(135deg, #6366f1, #4f46e5)'
                    : '#e0e7ff',
                  color: isEdited ? 'white' : '#6b7280',
                  border: isEdited ? 'none' : '1.5px dashed #a5b4fc',
                  borderRadius: '12px',
                  padding: '12px 24px',
                  fontSize: '0.92rem',
                  fontWeight: 700,
                  cursor: !isEdited || fbStatus === 'submitting' || fbStatus === 'success' ? 'not-allowed' : 'pointer',
                  opacity: fbStatus === 'submitting' || fbStatus === 'success' ? 0.6 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  boxShadow: isEdited ? '0 4px 12px rgba(99,102,241,0.25)' : 'none',
                  transition: 'all 0.2s ease',
                }}
                onMouseOver={e => { if (isEdited && fbStatus !== 'success') e.currentTarget.style.transform = 'translateY(-2px)'; }}
                onMouseOut={e => { e.currentTarget.style.transform = 'translateY(0)'; }}
              >
                <span>✏️ Record Custom Deployment</span>
                {isEdited && (
                  <span style={{
                    background: 'rgba(255,255,255,0.25)',
                    borderRadius: '8px',
                    padding: '1px 7px',
                    fontSize: '0.72rem',
                    fontWeight: 800,
                    letterSpacing: '0.02em',
                  }}>Modified</span>
                )}
              </button>

              {fbStatus === 'submitting' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)', fontSize: '0.88rem' }}>
                  <span className="spinner" style={{ width: '16px', height: '16px' }} />
                  <span>Saving...</span>
                </div>
              )}
            </div>

            {/* Feedback message */}
            {fbMsg && (
              <div style={{
                marginTop: '16px',
                padding: '12px 16px',
                borderRadius: '10px',
                background: fbStatus === 'error' ? '#fef2f2' : '#f0fdf4',
                border: `1px solid ${fbStatus === 'error' ? '#fecaca' : '#bbf7d0'}`,
                color: fbStatus === 'error' ? '#dc2626' : '#16a34a',
                fontSize: '0.88rem',
                fontWeight: 600,
              }}>
                {fbMsg}
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
                    {simData.diversion_plan.normal_route.distance_km} km
                  </span>
                </div>
                {showDiversion ? (
                  <div className="metric-item">
                    <span className="metric-lbl">Via {simData.diversion_plan.alternate_corridor || 'Alternate'}</span>
                    <span className="metric-val" style={{ color: 'var(--color-green)' }}>
                      {simData.diversion_plan.diverted_route?.distance_km || 'n/a'} km
                    </span>
                  </div>
                ) : (
                  <div className="metric-item" style={{ justifyContent: 'center', alignItems: 'center', background: '#f8f9fa' }}>
                    <span className="metric-lbl" style={{ marginBottom: '10px' }}>Alternate Route</span>
                    <button
                      onClick={() => setShowDiversion(true)}
                      style={{
                        background: 'linear-gradient(150deg, #10b981, #059669)',
                        color: 'white',
                        border: 'none',
                        borderRadius: '10px',
                        padding: '10px 20px',
                        fontSize: '0.92rem',
                        fontWeight: '700',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '6px',
                        boxShadow: '0 4px 12px rgba(16, 185, 129, 0.2)',
                        transition: 'all 0.2s ease',
                        width: '85%',
                        textAlign: 'center'
                      }}
                      onMouseOver={(e) => {
                        e.currentTarget.style.transform = 'translateY(-2px)';
                        e.currentTarget.style.boxShadow = '0 6px 18px rgba(16, 185, 129, 0.35)';
                      }}
                      onMouseOut={(e) => {
                        e.currentTarget.style.transform = 'translateY(0)';
                        e.currentTarget.style.boxShadow = '0 4px 12px rgba(16, 185, 129, 0.2)';
                      }}
                    >
                      <span>🧭 Show Route</span>
                    </button>
                  </div>
                )}
              </div>

              {showDiversion && simData.diversion_plan.diverted_route && (
                <div style={{ fontSize: '0.88rem', fontWeight: 700, margin: '5px 0' }}>
                  Distance penalty: <span style={{ color: 'var(--color-red)' }}>
                    +{((simData.diversion_plan.diverted_route.distance_km || 0) - simData.diversion_plan.normal_route.distance_km).toFixed(2)} km
                  </span>
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
