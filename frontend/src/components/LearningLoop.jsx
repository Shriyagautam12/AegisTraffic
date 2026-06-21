import React, { useState, useEffect } from 'react';

export default function LearningLoop() {
  const [learningData, setLearningData] = useState(null);
  const [loading, setLoading] = useState(true);

  // Form states
  const [selectedPredId, setSelectedPredId] = useState('');
  const [actualSeverity, setActualSeverity] = useState('Medium');
  const [actualDuration, setActualDuration] = useState(90.0);
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState(null);

  // Tooltip state for scatter plot
  const [hoveredPoint, setHoveredPoint] = useState(null);

  const fetchLearningData = () => {
    setLoading(true);
    fetch('/api/learning')
      .then(res => res.json())
      .then(data => {
        setLearningData(data);
        if (data.open_predictions && data.open_predictions.length > 0) {
          setSelectedPredId(data.open_predictions[0].prediction_id);
        } else {
          setSelectedPredId('');
        }
        setLoading(false);
      })
      .catch(err => {
        console.error("Error fetching learning data: ", err);
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchLearningData();
  }, []);

  const handleRecordOutcome = (e) => {
    e.preventDefault();
    if (!selectedPredId) return;

    setSubmitting(true);
    setFeedback(null);

    const payload = {
      prediction_id: parseInt(selectedPredId),
      actual_severity: actualSeverity,
      actual_duration: parseFloat(actualDuration)
    };

    fetch('/api/learning/outcome', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(res => res.json())
      .then(data => {
        const isCorrect = data.severity_correct ? '✅ correct' : '❌ wrong';
        setFeedback(`Recorded outcome for prediction #${data.prediction_id} · Severity is ${isCorrect} · Duration error: ${Math.round(data.duration_error_mins)} min`);
        setSubmitting(false);
        fetchLearningData();
      })
      .catch(err => {
        console.error("Error recording outcome: ", err);
        setSubmitting(false);
        setFeedback("❌ Failed to record outcome.");
      });
  };

  if (loading && !learningData) {
    return (
      <div className="page-container" style={{ alignItems: 'center', justifyContent: 'center', height: '100%' }}>
        <span className="spinner"></span>
        <span style={{ marginTop: '10px', fontWeight: 600 }}>Loading learning data...</span>
      </div>
    );
  }

  const report = learningData?.report || {};
  const corrections = learningData?.corrections || [];
  const openPredictions = learningData?.open_predictions || [];
  const scatterData = learningData?.scatter_data || [];
  const comparisonData = learningData?.comparison_data || [];

  // ── SVG Scatter plot ──────────────────────────────────────────────────────────
  const renderScatterPlot = () => {
    if (scatterData.length === 0) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '280px', color: 'var(--text-muted)' }}>
          <span>📊</span>
          <span style={{ fontSize: '0.85rem', marginTop: '10px' }}>No outcome data yet. Approve or record deployments from the Event Simulator to populate this chart.</span>
        </div>
      );
    }

    const svgWidth = 420;
    const svgHeight = 280;
    const padding = 40;

    const maxVal = Math.max(
      ...scatterData.map(d => Math.max(d.pred_duration || 0, d.actual_duration || 0)),
      120
    ) * 1.15;

    const scaleX = (val) => padding + ((val / maxVal) * (svgWidth - padding * 2));
    const scaleY = (val) => svgHeight - padding - ((val / maxVal) * (svgHeight - padding * 2));

    return (
      <div style={{ position: 'relative', display: 'flex', justifyContent: 'center' }}>
        <svg width={svgWidth} height={svgHeight}>
          <line x1={padding} y1={padding} x2={padding} y2={svgHeight - padding} stroke="#e5e7eb" strokeWidth="1.5" />
          <line x1={padding} y1={svgHeight - padding} x2={svgWidth - padding} y2={svgHeight - padding} stroke="#e5e7eb" strokeWidth="1.5" />
          <line
            x1={scaleX(0)} y1={scaleY(0)}
            x2={scaleX(maxVal * 0.85)} y2={scaleY(maxVal * 0.85)}
            stroke="#9ca3af" strokeWidth="1.5" strokeDasharray="4, 4"
          />
          <text x={scaleX(maxVal * 0.75)} y={scaleY(maxVal * 0.75) - 6} fill="#9ca3af" fontSize="10" fontWeight="bold">perfect</text>

          {[0, maxVal * 0.25, maxVal * 0.5, maxVal * 0.75, maxVal * 0.95].map((val, idx) => (
            <g key={idx}>
              <line x1={scaleX(val)} y1={svgHeight - padding} x2={scaleX(val)} y2={svgHeight - padding + 4} stroke="#9ca3af" />
              <text x={scaleX(val)} y={svgHeight - padding + 16} fill="var(--text-muted)" fontSize="9" textAnchor="middle">{Math.round(val)}</text>
            </g>
          ))}
          {[0, maxVal * 0.25, maxVal * 0.5, maxVal * 0.75, maxVal * 0.95].map((val, idx) => (
            <g key={idx}>
              <line x1={padding - 4} y1={scaleY(val)} x2={padding} y2={scaleY(val)} stroke="#9ca3af" />
              <text x={padding - 8} y={scaleY(val) + 3} fill="var(--text-muted)" fontSize="9" textAnchor="end">{Math.round(val)}</text>
            </g>
          ))}

          <text x={svgWidth / 2} y={svgHeight - 4} fill="var(--text-secondary)" fontSize="10" fontWeight="700" textAnchor="middle">Predicted (min)</text>
          <text x="12" y={svgHeight / 2} fill="var(--text-secondary)" fontSize="10" fontWeight="700" textAnchor="middle" style={{ transform: `rotate(-90deg) translate(-${svgHeight / 2}px, -15px)`, transformOrigin: '0 0' }}>Actual (min)</text>

          {scatterData.map((pt, idx) => {
            const cx = scaleX(pt.pred_duration);
            const cy = scaleY(pt.actual_duration);
            return (
              <circle
                key={idx}
                cx={cx} cy={cy} r="7"
                fill="var(--color-blue)" stroke="#bfdbfe" strokeWidth="1.5"
                style={{ cursor: 'pointer', transition: 'all 0.1s' }}
                onMouseEnter={() => setHoveredPoint({ ...pt, cx, cy })}
                onMouseLeave={() => setHoveredPoint(null)}
              />
            );
          })}
        </svg>

        {hoveredPoint && (
          <div style={{
            position: 'absolute',
            left: `${hoveredPoint.cx + 10}px`,
            top: `${hoveredPoint.cy - 40}px`,
            background: 'rgba(15, 23, 42, 0.9)',
            color: 'white',
            padding: '6px 10px',
            borderRadius: '6px',
            fontSize: '0.74rem',
            zIndex: 1000,
            pointerEvents: 'none',
            display: 'flex',
            flexDirection: 'column',
            gap: '2px',
            boxShadow: '0 4px 8px rgba(0,0,0,0.15)'
          }}>
            <span style={{ fontWeight: 800, textTransform: 'capitalize' }}>{hoveredPoint.corridor}</span>
            <span>pred {Math.round(hoveredPoint.pred_duration)}m → actual {Math.round(hoveredPoint.actual_duration)}m</span>
          </div>
        )}
      </div>
    );
  };

  // ── Comparative Analysis ──────────────────────────────────────────────────────
  const RESOURCE_FIELDS = [
    { key: 'officers', label: 'Officers', predKey: 'pred_officers', actualKey: 'actual_officers', icon: '👮', color: 'var(--color-blue)' },
    { key: 'barricades', label: 'Barricades', predKey: 'pred_barricades', actualKey: 'actual_barricades', icon: '🚧', color: 'var(--color-gold-start)' },
    { key: 'patrol_jeeps', label: 'Patrol Jeeps', predKey: 'pred_patrol_jeeps', actualKey: 'actual_patrol_jeeps', icon: '🚔', color: 'var(--color-teal)' },
    { key: 'tow_vehicles', label: 'Tow Vehicles', predKey: 'pred_tow_vehicles', actualKey: 'actual_tow_vehicles', icon: '🚛', color: 'var(--color-red)' },
    { key: 'command_vans', label: 'Command Vans', predKey: 'pred_command_vans', actualKey: 'actual_command_vans', icon: '📡', color: 'var(--color-purple)' },
  ];

  const DiffBadge = ({ pred, actual }) => {
    if (pred == null || actual == null) return <span style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>—</span>;
    const diff = actual - pred;
    if (diff === 0) return (
      <span style={{ padding: '2px 8px', borderRadius: '10px', background: '#dcfce7', color: '#15803d', fontWeight: 700, fontSize: '0.72rem' }}>✓ Match</span>
    );
    return (
      <span style={{
        padding: '2px 8px',
        borderRadius: '10px',
        background: diff > 0 ? '#fee2e2' : '#e0f2fe',
        color: diff > 0 ? '#dc2626' : '#0369a1',
        fontWeight: 700,
        fontSize: '0.72rem',
      }}>
        {diff > 0 ? `+${diff}` : `${diff}`}
      </span>
    );
  };

  const renderComparativeAnalysis = () => {
    if (comparisonData.length === 0) {
      return (
        <div style={{
          padding: '28px',
          background: 'linear-gradient(135deg, #eff6ff, #f8f9ff)',
          borderRadius: '14px',
          border: '1px solid #bfdbfe',
          color: '#1e40af',
          fontSize: '0.9rem',
          lineHeight: 1.6,
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
          alignItems: 'flex-start',
        }}>
          <span style={{ fontSize: '1.5rem' }}>🤖</span>
          <strong>No operational outcomes recorded yet.</strong>
          <span>Go to the <strong>Event Simulator</strong> tab, generate a prediction, then click <em>"Approve Suggested Plan"</em> or <em>"Record Custom Deployment"</em> to start feeding the learning system.</span>
        </div>
      );
    }

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {comparisonData.map((row) => {
          const eventLabel = (row.event_cause || 'Unknown').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
          const corridorLabel = (row.corridor || 'Unknown').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
          const predSev = row.pred_severity || '—';
          const actualSev = row.actual_severity || '—';
          const sevMatch = predSev === actualSev;
          const dateStr = row.created_at ? new Date(row.created_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }) : '—';

          return (
            <div key={row.outcome_id} style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-color)',
              borderRadius: '16px',
              padding: '20px',
              position: 'relative',
              overflow: 'hidden',
            }}>
              {/* Event header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px', flexWrap: 'wrap', gap: '8px' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <span style={{ fontWeight: 800, fontSize: '0.95rem', color: 'var(--text-primary)' }}>
                    #{row.prediction_id} · {eventLabel}
                  </span>
                  <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                    {corridorLabel} · {dateStr}
                  </span>
                </div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Severity:</span>
                  <span style={{
                    padding: '3px 10px',
                    borderRadius: '10px',
                    background: predSev === 'High' ? '#fee2e2' : predSev === 'Medium' ? '#fef3c7' : '#dcfce7',
                    color: predSev === 'High' ? '#dc2626' : predSev === 'Medium' ? '#d97706' : '#16a34a',
                    fontSize: '0.75rem', fontWeight: 700,
                  }}>Pred: {predSev}</span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>→</span>
                  <span style={{
                    padding: '3px 10px',
                    borderRadius: '10px',
                    background: actualSev === 'High' ? '#fee2e2' : actualSev === 'Medium' ? '#fef3c7' : '#dcfce7',
                    color: actualSev === 'High' ? '#dc2626' : actualSev === 'Medium' ? '#d97706' : '#16a34a',
                    fontSize: '0.75rem', fontWeight: 700,
                    border: sevMatch ? '2px solid #22c55e' : '2px solid #f87171',
                  }}>Actual: {actualSev}</span>
                  {sevMatch
                    ? <span style={{ fontSize: '0.75rem', color: '#16a34a', fontWeight: 700 }}>✓</span>
                    : <span style={{ fontSize: '0.75rem', color: '#dc2626', fontWeight: 700 }}>✗</span>
                  }
                </div>
              </div>

              {/* Resource comparison table */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '10px' }}>
                {RESOURCE_FIELDS.map(({ key, label, predKey, actualKey, icon, color }) => {
                  const pred = row[predKey];
                  const actual = row[actualKey];
                  return (
                    <div key={key} style={{
                      background: 'var(--bg-card)',
                      border: '1px solid var(--border-color)',
                      borderRadius: '12px',
                      padding: '12px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '6px',
                      alignItems: 'center',
                    }}>
                      <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-secondary)' }}>{icon} {label}</span>
                      <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap', justifyContent: 'center' }}>
                        <div style={{ textAlign: 'center' }}>
                          <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>Pred</div>
                          <div style={{ fontWeight: 800, color, fontSize: '1rem' }}>{pred ?? '—'}</div>
                        </div>
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>→</span>
                        <div style={{ textAlign: 'center' }}>
                          <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>Actual</div>
                          <div style={{ fontWeight: 800, color: 'var(--text-primary)', fontSize: '1rem' }}>{actual ?? '—'}</div>
                        </div>
                      </div>
                      <DiffBadge pred={pred} actual={actual} />
                    </div>
                  );
                })}
              </div>

              {/* Duration comparison */}
              {(row.pred_duration != null || row.actual_duration != null) && (
                <div style={{ marginTop: '12px', display: 'flex', gap: '12px', alignItems: 'center', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  <span>⏱ Duration:</span>
                  <span>Predicted <strong>{row.pred_duration != null ? `${Math.round(row.pred_duration)}m` : '—'}</strong></span>
                  <span>→</span>
                  <span>Actual <strong>{row.actual_duration != null ? `${Math.round(row.actual_duration)}m` : '—'}</strong></span>
                  {row.duration_error != null && (
                    <span style={{
                      padding: '2px 8px',
                      borderRadius: '10px',
                      background: row.duration_error > 30 ? '#fee2e2' : '#f0fdf4',
                      color: row.duration_error > 30 ? '#dc2626' : '#16a34a',
                      fontWeight: 700,
                    }}>
                      Δ {Math.round(row.duration_error)}m off
                    </span>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="page-container">
      {/* Banner */}
      <div className="page-title-banner">
        <div className="page-title-icon" style={{ backgroundColor: '#e0f2fe', color: '#0369a1' }}>📈</div>
        <div className="page-title-info">
          <h1 className="page-title">Post-Event Learning</h1>
          <span className="page-subtitle">Every prediction is logged, compared to reality, and used to self-correct over time.</span>
        </div>
      </div>

      {/* Headline Performance stats */}
      <div className="glass-card">
        <div className="card-title card-title-border">System Performance</div>

        <div className="metrics-strip">
          <div className="metric-item">
            <span className="metric-lbl">Predictions Logged</span>
            <span className="metric-val" style={{ color: 'var(--color-blue)' }}>{report.total_predictions}</span>
          </div>

          <div className="metric-item">
            <span className="metric-lbl">Outcomes Recorded</span>
            <span className="metric-val" style={{ color: 'var(--color-purple)' }}>{report.total_outcomes}</span>
          </div>

          <div className="metric-item">
            <span className="metric-lbl">Severity Accuracy</span>
            <span className="metric-val" style={{ color: 'var(--color-teal)' }}>
              {report.severity_accuracy !== null ? `${Math.round(report.severity_accuracy * 100)}%` : '—'}
            </span>
          </div>

          <div className="metric-item">
            <span className="metric-lbl">Median Duration Error</span>
            <span className="metric-val" style={{ color: 'var(--color-gold-start)' }}>
              {report.median_duration_error_mins !== null ? `${Math.round(report.median_duration_error_mins)}m` : '—'}
            </span>
          </div>
        </div>
      </div>

      {/* Grid: Corrections and Scatter Plot */}
      <div className="learning-layout">
        {/* Corrections list */}
        <div className="glass-card" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="card-title card-title-border">🧠 Learned Corridor Corrections</div>

          <div style={{ flexGrow: 1, overflowY: 'auto', maxHeight: '310px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {corrections.length > 0 ? (
              <>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '10px', display: 'inline-block' }}>
                  Where the model has learned to adjust its duration estimates from observed reality.
                </span>
                {corrections.slice(0, 10).map((item) => {
                  const direction = item.correction_factor > 1 ? '▲ longer' : '▼ shorter';
                  return (
                    <div key={item.corridor} className="learned-correction-item">
                      <span className="correction-name">{item.corridor.replace('_', ' ')}</span>
                      <div className="text-right" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span className="correction-ratio">×{item.correction_factor.toFixed(2)}</span>
                        <span className="correction-dir">({direction} than predicted)</span>
                      </div>
                    </div>
                  );
                })}
              </>
            ) : (
              <div style={{ padding: '24px', background: '#eff6ff', borderRadius: '12px', border: '1px solid #bfdbfe', color: '#1e40af', fontSize: '0.88rem', lineHeight: '1.4' }}>
                🧠 <strong>No corrections learned yet</strong> — needs ≥5 closed outcomes per corridor. Approve plans on the Simulator to watch the system learn.
              </div>
            )}
          </div>
        </div>

        {/* Scatter Plot */}
        <div className="glass-card">
          <div className="card-title card-title-border">Predicted vs Actual (Duration)</div>
          {renderScatterPlot()}
        </div>
      </div>

      {/* ── Comparative Analysis ──────────────────────────────────────────────── */}
      <div className="glass-card">
        <div className="card-title card-title-border" style={{ borderColor: 'var(--color-purple)' }}>
          🔬 Comparative Analysis — Predicted vs. Actually Deployed
        </div>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '20px' }}>
          A side-by-side breakdown of what the system recommended vs. what was actually deployed. 
          Difference badges highlight over- or under-allocation across all resource types.
        </p>
        {renderComparativeAnalysis()}
        {comparisonData.length > 0 && (
          <div style={{ marginTop: '16px', display: 'flex', gap: '14px', flexWrap: 'wrap', fontSize: '0.76rem', color: 'var(--text-muted)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ padding: '2px 8px', borderRadius: '10px', background: '#dcfce7', color: '#15803d', fontWeight: 700 }}>✓ Match</span> Perfect match
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ padding: '2px 8px', borderRadius: '10px', background: '#fee2e2', color: '#dc2626', fontWeight: 700 }}>+N</span> More deployed than predicted
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ padding: '2px 8px', borderRadius: '10px', background: '#e0f2fe', color: '#0369a1', fontWeight: 700 }}>−N</span> Fewer deployed than predicted
            </span>
          </div>
        )}
      </div>

      {/* Demo Outcome Recording Form */}
      <div className="glass-card">
        <div className="card-title card-title-border">🔁 Record an Outcome (simulate event closing)</div>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '20px' }}>
          In production this fills automatically when an officer closes an incident. Here you can manually link outcomes to open predictions to watch the system self-correct.
        </p>

        {openPredictions.length > 0 ? (
          <form onSubmit={handleRecordOutcome} className="outcome-form-inner">
            <div className="form-group">
              <label className="form-label">Open prediction</label>
              <select
                className="form-input"
                value={selectedPredId}
                onChange={(e) => setSelectedPredId(e.target.value)}
              >
                {openPredictions.map(p => (
                  <option key={p.prediction_id} value={p.prediction_id}>
                    #{p.prediction_id} · {p.corridor} · pred {p.pred_severity} {Math.round(p.pred_duration)}m
                  </option>
                ))}
              </select>
            </div>

            <div className="input-grid-3" style={{ gridTemplateColumns: '1fr 1fr 1fr' }}>
              <div className="form-group">
                <label className="form-label">Actual severity</label>
                <select
                  className="form-input"
                  value={actualSeverity}
                  onChange={(e) => setActualSeverity(e.target.value)}
                >
                  <option value="High">High</option>
                  <option value="Medium">Medium</option>
                  <option value="Low">Low</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Actual clearance (min)</label>
                <input
                  type="number"
                  min="1"
                  className="form-input"
                  value={actualDuration}
                  onChange={(e) => setActualDuration(e.target.value)}
                />
              </div>

              <div style={{ display: 'flex', alignItems: 'flex-end' }}>
                <button type="submit" className="submit-btn" disabled={submitting || !selectedPredId} style={{ height: '46px' }}>
                  {submitting ? 'Recording...' : 'Record outcome'}
                </button>
              </div>
            </div>

            {feedback && (
              <div style={{
                marginTop: '10px',
                padding: '10px 14px',
                background: feedback.startsWith('❌') ? '#fdeceb' : '#e9f7ee',
                border: feedback.startsWith('❌') ? '1px solid #f3b6b1' : '1px solid #b6e3c6',
                color: feedback.startsWith('❌') ? '#d6453b' : '#2f9e57',
                borderRadius: '8px',
                fontSize: '0.85rem',
                fontWeight: 600
              }}>
                {feedback}
              </div>
            )}
          </form>
        ) : (
          <div style={{ padding: '16px', background: '#f8f9fa', borderRadius: '12px', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', fontSize: '0.88rem' }}>
            🔮 No open predictions. Create simulations on the Simulator page and approve/record deployments to feed the learning system.
          </div>
        )}
      </div>

    </div>
  );
}
