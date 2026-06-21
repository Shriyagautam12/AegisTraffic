import React, { useState, useRef, useEffect } from 'react';

export default function AICopilot() {
  const EXAMPLES = [
    "Cricket match at Chinnaswamy, CBD 2, Friday 7pm with road closure. What should we do?",
    "There is a procession on Mysore Road tomorrow night.",
    "A truck has broken down on Tumkur Road this morning.",
    "VIP convoy on Bellary Road 1 at 10am.",
    "ನಾಳೆ ರಾತ್ರಿ ಮೈಸೂರು ರಸ್ತೆಯಲ್ಲಿ ಮೆರವಣಿಗೆ ಇದೆ. ಏನು ಮಾಡಬೇಕು?"
  ];

  const [chatHistory, setChatHistory] = useState([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [copilotMode, setCopilotMode] = useState('Checking mode...');

  const chatEndRef = useRef(null);

  // Auto-scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, loading]);

  // Initial ping to check API and Mode
  useEffect(() => {
    // Run a dummy quick check or default to Gemini live
    setCopilotMode('Gemini (live)');
  }, []);

  // Send message handler
  const handleSend = (textToSend) => {
    const text = textToSend || query;
    if (!text.trim()) return;

    // Add user question to history
    const userTurn = { type: 'user', content: text };
    setChatHistory(prev => [...prev, userTurn]);

    if (!textToSend) setQuery('');
    setLoading(true);

    fetch('/api/copilot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: text })
    })
      .then(res => res.json())
      .then(data => {
        // Build used context sources description
        const used = [];
        const ctx = data.context || {};
        if (ctx.prediction) used.push("ML prediction");
        if (ctx.precedent && ctx.precedent.examples) used.push(`${ctx.precedent.examples.length} similar events`);
        if (ctx.resources) used.push("resource plan");

        const aiTurn = {
          type: 'ai',
          content: data.answer,
          source: data.source,
          used: used.join(', ') || 'context'
        };

        setChatHistory(prev => [...prev, aiTurn]);
        setLoading(false);
      })
      .catch(err => {
        console.error("Copilot error: ", err);
        const errorTurn = {
          type: 'ai',
          content: "Sorry, I encountered an error while processing your request. Please try again.",
          source: "error",
          used: ""
        };
        setChatHistory(prev => [...prev, errorTurn]);
        setLoading(false);
      });
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSend();
    }
  };

  const clearChat = () => {
    setChatHistory([]);
  };

  return (
    <div className="page-container" style={{ display: 'grid', gridTemplateColumns: '3fr 1fr', gap: '30px', flexGrow: 1 }}>

      {/* Left Chat Window */}
      <div className="flex-column-gap-10" style={{ height: '100%', gap: '15px' }}>
        {/* Banner */}
        <div className="page-title-banner" style={{ marginBottom: '0' }}>
          <div className="page-title-icon" style={{ backgroundColor: '#fed7aa', color: '#ea580c' }}>💬</div>
          <div className="page-title-info">
            <h1 className="page-title">Ask AegisTraffic</h1>
            <span className="page-subtitle">
              Natural-language command copilot · English & ಕನ್ನಡ · Mode: <strong>{copilotMode}</strong>
            </span>
          </div>
        </div>

        {/* Chat History Panel */}
        <div className="chat-container">
          <div className="chat-history">
            {chatHistory.length === 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-secondary)', gap: '10px' }}>
                <span style={{ fontSize: '2.5rem' }}>🛡️</span>
                <span style={{ fontWeight: 700, fontSize: '1rem' }}>AegisTraffic Command Copilot</span>
                <span style={{ fontSize: '0.82rem', maxWidth: '300px', textAlign: 'center', lineHeight: '1.4' }}>
                  Ask any operational questions about traffic closures, events, and corridor resource deployments.
                </span>
              </div>
            )}

            {chatHistory.map((turn, idx) => (
              <React.Fragment key={idx}>
                {turn.type === 'user' ? (
                  <div className="chat-bubble-user">{turn.content}</div>
                ) : (
                  <>
                    <div className="chat-bubble-ai">{turn.content}</div>
                    {turn.used && (
                      <div className="chat-bubble-meta">
                        🔎 {turn.source} · grounded in: {turn.used}
                      </div>
                    )}
                  </>
                )}
              </React.Fragment>
            ))}

            {loading && (
              <div className="chat-bubble-ai" style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '12px 20px' }}>
                <span className="spinner" style={{ width: '16px', height: '16px' }}></span>
                <span style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>AegisTraffic is analyzing...</span>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Input block */}
          <div className="chat-input-bar">
            <input
              type="text"
              className="chat-input"
              placeholder="Ask about an event, incident, or corridor..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={loading}
            />
            <button className="chat-send-btn" onClick={() => handleSend()} disabled={loading || !query.trim()}>
              <span>➔</span>
            </button>
          </div>
        </div>
      </div>

      {/* Right Suggestion Sidebar */}
      <div className="flex-column-gap-10" style={{ gap: '20px' }}>
        <div className="glass-card" style={{ height: 'fit-content' }}>
          <div className="card-title card-title-border">Try an example</div>
          <div className="copilot-sidebar-card">
            {EXAMPLES.map(ex => (
              <button
                key={ex}
                className="suggestion-chip"
                onClick={() => handleSend(ex)}
                disabled={loading}
              >
                {ex}
              </button>
            ))}
          </div>
        </div>

        <button
          className="submit-btn"
          onClick={clearChat}
          style={{ background: '#f1f5f9', color: '#334155', border: '1px solid var(--border-color)', boxShadow: 'none' }}
        >
          🗑️ Clear chat
        </button>
      </div>

    </div>
  );
}
