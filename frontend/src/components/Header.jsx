import React, { useState, useEffect } from 'react';
import { Shield, Menu } from 'lucide-react';

export default function Header({ isCollapsed, setIsCollapsed }) {
  const [timeStr, setTimeStr] = useState('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      // Format to matching Bengaluru timezone IST (UTC+5:30)
      const options = {
        timeZone: 'Asia/Kolkata',
        weekday: 'short',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
      };

      const formatter = new Intl.DateTimeFormat('en-US', options);
      const parts = formatter.formatToParts(now);

      let weekday = '';
      let hour = '';
      let minute = '';

      parts.forEach(part => {
        if (part.type === 'weekday') weekday = part.value.toUpperCase();
        if (part.type === 'hour') hour = part.value;
        if (part.type === 'minute') minute = part.value;
      });

      setTimeStr(`${weekday} ${hour}:${minute} IST`);
    };

    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="top-header">
      <div className="header-left">
        <button
          className="sidebar-toggle-btn-top"
          onClick={() => setIsCollapsed(!isCollapsed)}
          title="Toggle Sidebar"
        >
          <Menu size={20} />
        </button>
        <div className="brand-logo header-logo">
          <Shield size={22} color="white" strokeWidth={2.5} />
        </div>
        <div className="brand-info">
          <span className="brand-name">AegisTraffic</span>
          <span className="brand-tag">Bengaluru Traffic Command</span>
        </div>
      </div>
      <div className="header-right">
        <div className="header-time">{timeStr}</div>
        <div className="header-user" title="Officer in Charge">OC</div>
      </div>
    </header>
  );
}
