import React, { useState, useEffect } from 'react';

export default function Header() {
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
        <span className="header-tagline">Bengaluru City Traffic Police</span>
      </div>
      <div className="header-right">
        <div className="header-time">{timeStr}</div>
        <div className="header-user" title="Officer in Charge">OC</div>
      </div>
    </header>
  );
}
