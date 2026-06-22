import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import RiskIntelligence from './components/RiskIntelligence';
import EventSimulator from './components/EventSimulator';
import AICopilot from './components/AICopilot';
import LearningLoop from './components/LearningLoop';

export default function App() {
  const [activeTab, setActiveTab] = useState('risk-intelligence');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [overviewData, setOverviewData] = useState(null);

  // Fetch metrics on mount to pass down to subcomponents
  useEffect(() => {
    fetch('/api/overview')
      .then(res => res.json())
      .then(data => {
        setOverviewData(data);
      })
      .catch(err => console.error("Error fetching overview metrics: ", err));
  }, []);

  const renderActiveView = () => {
    switch (activeTab) {
      case 'risk-intelligence':
        return <RiskIntelligence overviewData={overviewData} />;
      case 'simulator':
        return <EventSimulator />;
      case 'copilot':
        return <AICopilot />;
      case 'learning':
        return <LearningLoop />;
      default:
        return <RiskIntelligence overviewData={overviewData} />;
    }
  };

  return (
    <div className="app-container" style={{ flexDirection: 'column' }}>
      {/* Dynamic IST Top Header */}
      <Header isCollapsed={isSidebarCollapsed} setIsCollapsed={setIsSidebarCollapsed} />

      {/* Main Body */}
      <div className="app-body" style={{ display: 'flex', flexGrow: 1, overflow: 'hidden' }}>
        {/* Collabsible Sidebar */}
        <Sidebar
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          isCollapsed={isSidebarCollapsed}
          setIsCollapsed={setIsSidebarCollapsed}
        />

        {/* Main Container */}
        <div className="main-content">
          {renderActiveView()}
        </div>
      </div>
    </div>
  );
}
