import React from 'react';

export default function Sidebar({ activeTab, setActiveTab, isCollapsed, setIsCollapsed }) {
  const navItems = [
    { id: 'risk-intelligence', label: 'Risk Intelligence', icon: '🗺️' },
    { id: 'simulator', label: 'Event Simulator', icon: '🔮' },
    { id: 'copilot', label: 'AI Copilot', icon: '💬' },
    { id: 'learning', label: 'Learning Loop', icon: '📈' },
  ];

  return (
    <div className={`sidebar ${isCollapsed ? 'collapsed' : ''}`}>
      {/* Brand logo & info */}
      <div className="brand-area">
        <div className="brand-logo">🛡️</div>
        <div className="brand-info">
          <span className="brand-name">AegisTraffic</span>
          <span className="brand-tag">Bengaluru Traffic Command</span>
        </div>
      </div>

      <div className="workspace-label">Workspace</div>

      {/* Navigation */}
      <nav className="nav-links">
        {navItems.map((item) => (
          <button
            key={item.id}
            className={`nav-item ${activeTab === item.id ? 'active' : ''}`}
            onClick={() => setActiveTab(item.id)}
          >
            <span className="nav-icon">{item.icon}</span>
            <span className="nav-text">{item.label}</span>
          </button>
        ))}
      </nav>

      {/* Sidebar Footer */}
      <div className="sidebar-footer">
        <div className="footer-card">
          <div className="footer-card-inner">
            <span className="footer-icon">🚖</span>
            <div className="footer-text">
              <span className="footer-lbl">Powered by</span>
              <span className="footer-val">Namma Yatri</span>
            </div>
          </div>
        </div>

        <button
          className="sidebar-toggle-btn"
          onClick={() => setIsCollapsed(!isCollapsed)}
          title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
        >
          {isCollapsed ? '>>' : '<<'}
        </button>
      </div>
    </div>
  );
}
