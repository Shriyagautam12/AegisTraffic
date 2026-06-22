import { Map, PlayCircle, MessageSquare, TrendingUp } from 'lucide-react';

export default function Sidebar({ activeTab, setActiveTab, isCollapsed }) {
  const navItems = [
    { id: 'risk-intelligence', label: 'Risk Intelligence', icon: <Map size={18} /> },
    { id: 'simulator', label: 'Event Simulator', icon: <PlayCircle size={18} /> },
    { id: 'copilot', label: 'AI Copilot', icon: <MessageSquare size={18} /> },
    { id: 'learning', label: 'Post-Event Learning', icon: <TrendingUp size={18} /> },
  ];

  return (
    <div className={`sidebar ${isCollapsed ? 'collapsed' : ''}`}>

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
    </div>
  );
}
