import React, { useState, useEffect, useRef } from "react";

export interface SubsystemHealth {
  status: string;
  last_update: string;
  processing_latency_ms: number;
  message_count: number;
  replay_status: string;
}

export interface DashboardSnapshot {
  snapshot_id: string;
  symbol: string;
  timeframe: string;
  market_state?: any;
  pattern_state?: any;
  pattern_quality?: any;
  confluence?: any;
  strategy?: any;
  trading_context?: any;
  risk_assessment?: any;
  position_size?: any;
  health_status: Record<string, SubsystemHealth>;
  timestamp: string;
  version: string;
}

export interface HistoricalEvent {
  event_id: string;
  timestamp: string;
  subsystem: string;
  event_name: string;
  symbol: string;
  timeframe: string;
  latency_ms: number;
  severity: string;
  payload: any;
}

export interface LogEntry {
  timestamp: string;
  message: string;
  severity: "info" | "warn" | "error";
}

export default function App() {
  const [activeTab, setActiveTab] = useState<string>("dashboard");
  const [health, setHealth] = useState<Record<string, SubsystemHealth>>({});
  const [snapshots, setSnapshots] = useState<DashboardSnapshot[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [events, setEvents] = useState<HistoricalEvent[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState<string>("");
  const [selectedTimeframe, setSelectedTimeframe] = useState<string>("");
  const [wsSystemConnected, setWsSystemConnected] = useState<boolean>(false);
  const [wsLogsConnected, setWsLogsConnected] = useState<boolean>(false);

  const systemWsRef = useRef<WebSocket | null>(null);
  const logsWsRef = useRef<WebSocket | null>(null);

  const addLog = (message: string, severity: "info" | "warn" | "error" = "info") => {
    const now = new Date();
    const timestamp = now.toLocaleTimeString() + "." + String(now.getMilliseconds()).padStart(3, "0");
    setLogs((prev) => [...prev, { timestamp, message, severity }].slice(-500));
  };

  // REST API loading
  const fetchInitialData = async () => {
    try {
      const healthRes = await fetch("/health");
      const healthData = await healthRes.json();
      setHealth(healthData);

      const snapRes = await fetch("/dashboard");
      const snapData = await snapRes.json();
      setSnapshots(snapData);

      const eventsRes = await fetch("/events");
      const eventsData = await eventsRes.json();
      setEvents(eventsData);

      addLog("Successfully loaded state data from REST API.", "info");
    } catch (e) {
      addLog("REST API connection failed. Retrying in background...", "error");
    }
  };

  useEffect(() => {
    fetchInitialData();
    const interval = setInterval(fetchInitialData, 10000);
    return () => clearInterval(interval);
  }, []);

  // WebSockets setup
  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host || "localhost:8000";

    // System WebSocket
    const systemWs = new WebSocket(`${protocol}//${host}/ws/system`);
    systemWsRef.current = systemWs;

    systemWs.onopen = () => {
      setWsSystemConnected(true);
      addLog("Connected to WebSocket channel: system", "info");
    };

    systemWs.onmessage = (event) => {
      try {
        const snapshot = JSON.parse(event.data) as DashboardSnapshot;
        setSnapshots((prev) => {
          const idx = prev.findIndex((s) => s.symbol === snapshot.symbol && s.timeframe === snapshot.timeframe);
          if (idx >= 0) {
            const newSnaps = [...prev];
            newSnaps[idx] = snapshot;
            return newSnaps;
          } else {
            return [...prev, snapshot];
          }
        });
        if (snapshot.health_status) {
          setHealth(snapshot.health_status);
        }
      } catch (e) {
        addLog(`Failed to parse system WS data: ${event.data}`, "warn");
      }
    };

    systemWs.onclose = () => {
      setWsSystemConnected(false);
      addLog("Disconnected from WebSocket channel: system", "warn");
    };

    // Logs WebSocket
    const logsWs = new WebSocket(`${protocol}//${host}/ws/logs`);
    logsWsRef.current = logsWs;

    logsWs.onopen = () => {
      setWsLogsConnected(true);
      addLog("Connected to WebSocket channel: logs", "info");
    };

    logsWs.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        addLog(data.message, data.severity || "info");
      } catch (e) {
        addLog(`Failed to parse logs WS data: ${event.data}`, "warn");
      }
    };

    logsWs.onclose = () => {
      setWsLogsConnected(false);
      addLog("Disconnected from WebSocket channel: logs", "warn");
    };

    return () => {
      systemWs.close();
      logsWs.close();
    };
  }, []);

  const activeSymbols = Array.from(new Set(snapshots.map((s) => s.symbol)));
  const activeTimeframes = Array.from(new Set(snapshots.map((s) => s.timeframe)));

  const filteredSnapshots = snapshots.filter((s) => {
    if (selectedSymbol && s.symbol !== selectedSymbol) return false;
    if (selectedTimeframe && s.timeframe !== selectedTimeframe) return false;
    return true;
  });

  const activeSnapshot = filteredSnapshots[0] || null;

  return (
    <div className="container">
      <header>
        <div className="logo-section">
          <i className="fa-solid fa-cube fa-xl" style={{ color: "var(--accent)" }}></i>
          <h1>TOJI observatory</h1>
        </div>
        <ul className="nav-links">
          <li className={`nav-item ${activeTab === "dashboard" ? "active" : ""}`} onClick={() => setActiveTab("dashboard")}>
            <i className="fa-solid fa-gauge"></i> Dashboard
          </li>
          <li className={`nav-item ${activeTab === "market" ? "active" : ""}`} onClick={() => setActiveTab("market")}>
            <i className="fa-solid fa-chart-line"></i> Market
          </li>
          <li className={`nav-item ${activeTab === "patterns" ? "active" : ""}`} onClick={() => setActiveTab("patterns")}>
            <i className="fa-solid fa-shapes"></i> Patterns
          </li>
          <li className={`nav-item ${activeTab === "confluence" ? "active" : ""}`} onClick={() => setActiveTab("confluence")}>
            <i className="fa-solid fa-circle-nodes"></i> Confluence
          </li>
          <li className={`nav-item ${activeTab === "strategy" ? "active" : ""}`} onClick={() => setActiveTab("strategy")}>
            <i className="fa-solid fa-brain"></i> Strategy
          </li>
          <li className={`nav-item ${activeTab === "risk" ? "active" : ""}`} onClick={() => setActiveTab("risk")}>
            <i className="fa-solid fa-shield-halved"></i> Risk
          </li>
          <li className={`nav-item ${activeTab === "position" ? "active" : ""}`} onClick={() => setActiveTab("position")}>
            <i className="fa-solid fa-scale-balanced"></i> Sizing
          </li>
          <li className={`nav-item ${activeTab === "logs" ? "active" : ""}`} onClick={() => setActiveTab("logs")}>
            <i className="fa-solid fa-terminal"></i> Console
          </li>
        </ul>
        <div className={`live-status ${(!wsSystemConnected || !wsLogsConnected) ? "disconnected" : ""}`}>
          <div className="ping-dot"></div>
          {wsSystemConnected && wsLogsConnected ? "WS STREAMING" : "WS OFFLINE"}
        </div>
      </header>

      <main>
        {/* Filter Bar */}
        <div className="filter-bar">
          <i className="fa-solid fa-filter" style={{ color: "var(--text-muted)" }}></i>
          <span style={{ fontSize: "0.9rem", color: "var(--text-muted)" }}>Filter Snapshots:</span>
          <select className="filter-select" value={selectedSymbol} onChange={(e) => setSelectedSymbol(e.target.value)}>
            <option value="">All Symbols</option>
            {activeSymbols.map((sym) => <option key={sym} value={sym}>{sym}</option>)}
          </select>
          <select className="filter-select" value={selectedTimeframe} onChange={(e) => setSelectedTimeframe(e.target.value)}>
            <option value="">All Timeframes</option>
            {activeTimeframes.map((tf) => <option key={tf} value={tf}>{tf}</option>)}
          </select>
        </div>

        {/* TAB CONTENTS */}
        {activeTab === "dashboard" && (
          <React.Fragment>
            {/* Health diagnostics */}
            <div className="card primary">
              <div className="card-title">
                <span><i className="fa-solid fa-heart-pulse"></i> Subsystem Diagnostics</span>
                <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Real-time Observability Monitor</span>
              </div>
              <div className="health-grid">
                {Object.entries(health).map(([sub, data]) => (
                  <div key={sub} className="health-item">
                    <span style={{ fontSize: "0.9rem", fontWeight: 600 }}>{sub}</span>
                    <span className={`health-badge status-${data.status.toLowerCase()}`}>{data.status}</span>
                    <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>{data.message_count} msgs</span>
                    <span style={{ fontSize: "0.7rem", color: "var(--accent)" }}>{data.processing_latency_ms.toFixed(1)} ms</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Overview Grid */}
            <div className="dashboard-grid">
              {/* Market States */}
              <div className="card accent">
                <div className="card-title">
                  <span><i className="fa-solid fa-chart-line"></i> Market States Overview</span>
                </div>
                {filteredSnapshots.map((snap) => (
                  <div key={snap.snapshot_id} style={{ marginBottom: "1rem", borderBottom: "1px solid var(--border-color)", paddingBottom: "0.8rem" }}>
                    <div className="metric-group">
                      <span style={{ fontWeight: 700 }}>{snap.symbol} ({snap.timeframe})</span>
                      <span className="metric-value highlight">{snap.market_state?.trend?.direction || "RANGING"}</span>
                    </div>
                    <div className="metric-group">
                      <span className="metric-label">BOS Breakout History</span>
                      <span className="metric-value">{snap.market_state?.bos_history?.length || 0} events</span>
                    </div>
                  </div>
                ))}
                {filteredSnapshots.length === 0 && <p style={{ color: "var(--text-muted)" }}>No active market state snapshots found.</p>}
              </div>

              {/* Risk Engine */}
              <div className="card danger">
                <div className="card-title">
                  <span><i className="fa-solid fa-triangle-exclamation"></i> Risk Engine Decider</span>
                </div>
                {activeSnapshot && activeSnapshot.risk_assessment ? (
                  <div>
                    <div className="metric-group">
                      <span className="metric-label">Overall Safety Score</span>
                      <span style={{
                        color: activeSnapshot.risk_assessment.overall_score >= 85 ? "var(--success)" :
                               activeSnapshot.risk_assessment.overall_score >= 80 ? "var(--warning)" : "var(--danger)",
                        fontWeight: 700,
                        fontSize: "1.25rem"
                      }}>{activeSnapshot.risk_assessment.overall_score.toFixed(1)} / 100</span>
                    </div>
                    <div className="metric-group">
                      <span className="metric-label">Risk Decision Permit</span>
                      <span className={`health-badge status-${activeSnapshot.risk_assessment.decision.toLowerCase()}`}>{activeSnapshot.risk_assessment.decision}</span>
                    </div>
                    <div style={{ marginTop: "0.8rem" }}>
                      <span className="metric-label" style={{ fontSize: "0.8rem" }}>Violations timeline:</span>
                      {activeSnapshot.risk_assessment.violations && activeSnapshot.risk_assessment.violations.map((v: string, i: number) => (
                        <p key={i} style={{ fontSize: "0.8rem", color: "var(--danger)", marginTop: "0.2rem" }}><i className="fa-solid fa-circle-xmark"></i> {v}</p>
                      ))}
                      {(!activeSnapshot.risk_assessment.violations || activeSnapshot.risk_assessment.violations.length === 0) && (
                        <p style={{ fontSize: "0.8rem", color: "var(--success)", marginTop: "0.2rem" }}><i className="fa-solid fa-circle-check"></i> No risk limits breached.</p>
                      )}
                    </div>
                  </div>
                ) : <p style={{ color: "var(--text-muted)" }}>Select a symbol/timeframe filter to load risk data.</p>}
              </div>

              {/* Position Sizing */}
              <div className="card success">
                <div className="card-title">
                  <span><i className="fa-solid fa-coins"></i> Capital Sizer</span>
                </div>
                {activeSnapshot && activeSnapshot.position_size ? (
                  <div>
                    <div className="metric-group">
                      <span className="metric-label">Sizing Status</span>
                      <span className="metric-value">{activeSnapshot.position_size.status || "UNSIZED"}</span>
                    </div>
                    {activeSnapshot.position_size.position_size && (
                      <React.Fragment>
                        <div className="metric-group">
                          <span className="metric-label">Calculated Base Qty</span>
                          <span className="metric-value highlight">{activeSnapshot.position_size.position_size.quantity.toFixed(4)}</span>
                        </div>
                        <div className="metric-group">
                          <span className="metric-label">Required Leverage</span>
                          <span className="metric-value">{activeSnapshot.position_size.position_size.leverage.toFixed(2)}x</span>
                        </div>
                        <div className="metric-group">
                          <span className="metric-label">Margin Required</span>
                          <span className="metric-value">${activeSnapshot.position_size.position_size.margin_required.toFixed(2)}</span>
                        </div>
                      </React.Fragment>
                    )}
                  </div>
                ) : <p style={{ color: "var(--text-muted)" }}>Select a symbol/timeframe filter to load position sizing.</p>}
              </div>
            </div>
          </React.Fragment>
        )}

        {activeTab === "market" && (
          <div className="card accent">
            <div className="card-title">
              <span><i className="fa-solid fa-chart-line"></i> Market State Details</span>
            </div>
            {activeSnapshot && activeSnapshot.market_state ? (
              <div>
                <pre style={{ background: "rgba(0,0,0,0.2)", padding: "1rem", borderRadius: "8px", overflowX: "auto", fontSize: "0.85rem" }}>
                  {JSON.stringify(activeSnapshot.market_state, null, 2)}
                </pre>
              </div>
            ) : <p style={{ color: "var(--text-muted)" }}>Select a symbol/timeframe filter containing market state observations.</p>}
          </div>
        )}

        {activeTab === "patterns" && (
          <div className="card primary">
            <div className="card-title">
              <span><i className="fa-solid fa-shapes"></i> Price Action Patterns</span>
            </div>
            {activeSnapshot && activeSnapshot.pattern_state ? (
              <div>
                <pre style={{ background: "rgba(0,0,0,0.2)", padding: "1rem", borderRadius: "8px", overflowX: "auto", fontSize: "0.85rem" }}>
                  {JSON.stringify(activeSnapshot.pattern_state, null, 2)}
                </pre>
              </div>
            ) : <p style={{ color: "var(--text-muted)" }}>Select a symbol/timeframe filter containing pattern matches.</p>}
          </div>
        )}

        {activeTab === "confluence" && (
          <div className="card accent">
            <div className="card-title">
              <span><i className="fa-solid fa-circle-nodes"></i> Confluence Scores</span>
            </div>
            {activeSnapshot && activeSnapshot.confluence ? (
              <div>
                <pre style={{ background: "rgba(0,0,0,0.2)", padding: "1rem", borderRadius: "8px", overflowX: "auto", fontSize: "0.85rem" }}>
                  {JSON.stringify(activeSnapshot.confluence, null, 2)}
                </pre>
              </div>
            ) : <p style={{ color: "var(--text-muted)" }}>Select a symbol/timeframe filter containing confluence score matrices.</p>}
          </div>
        )}

        {activeTab === "strategy" && (
          <div className="card primary">
            <div className="card-title">
              <span><i className="fa-solid fa-brain"></i> Strategy Signals</span>
            </div>
            {activeSnapshot && activeSnapshot.strategy ? (
              <div>
                <pre style={{ background: "rgba(0,0,0,0.2)", padding: "1rem", borderRadius: "8px", overflowX: "auto", fontSize: "0.85rem" }}>
                  {JSON.stringify(activeSnapshot.strategy, null, 2)}
                </pre>
              </div>
            ) : <p style={{ color: "var(--text-muted)" }}>Select a symbol/timeframe filter containing active strategy signals.</p>}
          </div>
        )}

        {activeTab === "risk" && (
          <div className="card danger">
            <div className="card-title">
              <span><i className="fa-solid fa-shield-halved"></i> Risk Assessments</span>
            </div>
            {activeSnapshot && activeSnapshot.risk_assessment ? (
              <div>
                <pre style={{ background: "rgba(0,0,0,0.2)", padding: "1rem", borderRadius: "8px", overflowX: "auto", fontSize: "0.85rem" }}>
                  {JSON.stringify(activeSnapshot.risk_assessment, null, 2)}
                </pre>
              </div>
            ) : <p style={{ color: "var(--text-muted)" }}>Select a symbol/timeframe filter containing risk assessments.</p>}
          </div>
        )}

        {activeTab === "position" && (
          <div className="card success">
            <div className="card-title">
              <span><i className="fa-solid fa-scale-balanced"></i> Capital Allocation</span>
            </div>
            {activeSnapshot && activeSnapshot.position_size ? (
              <div>
                <pre style={{ background: "rgba(0,0,0,0.2)", padding: "1rem", borderRadius: "8px", overflowX: "auto", fontSize: "0.85rem" }}>
                  {JSON.stringify(activeSnapshot.position_size, null, 2)}
                </pre>
              </div>
            ) : <p style={{ color: "var(--text-muted)" }}>Select a symbol/timeframe filter containing position sizing parameters.</p>}
          </div>
        )}

        {activeTab === "logs" && (
          <React.Fragment>
            <div className="card">
              <div className="card-title">
                <span><i className="fa-solid fa-terminal"></i> Platform Logs Console</span>
              </div>
              <div className="log-console">
                {logs.map((log, idx) => (
                  <div key={idx} className={`log-entry ${log.severity}`}>
                    [{log.timestamp}] {log.message}
                  </div>
                ))}
              </div>
            </div>

            <div className="card" style={{ marginTop: "1.5rem" }}>
              <div className="card-title">
                <span><i className="fa-solid fa-timeline"></i> Event Dispatches Timeline</span>
              </div>
              <div className="timeline">
                {events.map((e) => (
                  <div key={e.event_id} className="timeline-item">
                    <div className="timeline-content">
                      <div className="timeline-header">
                        <span className="timeline-subsystem">{e.subsystem}</span>
                        <span className="timeline-time">{new Date(e.timestamp).toLocaleTimeString()}</span>
                      </div>
                      <p style={{ fontWeight: 600, fontSize: "0.9rem" }}>{e.event_name}</p>
                      <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "0.2rem" }}>
                        Target: {e.symbol}/{e.timeframe} | Latency: {e.latency_ms.toFixed(1)}ms
                      </p>
                    </div>
                  </div>
                ))}
                {events.length === 0 && <p style={{ color: "var(--text-muted)" }}>No timeline events recorded yet.</p>}
              </div>
            </div>
          </React.Fragment>
        )}
      </main>

      <footer>
        &copy; 2026 Toji Trading System - Observability Platform. Built with React and FastAPI.
      </footer>
    </div>
  );
}
