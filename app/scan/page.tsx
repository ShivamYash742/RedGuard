"use client"
import { useState, useEffect } from 'react'

interface Agent {
  id: string
  name: string
  description: string
  is_default: boolean
}

export default function LiveScan() {
  const [running, setRunning]   = useState(false)
  const [events, setEvents]     = useState<any[]>([])
  const [progress, setProgress] = useState({ current: 0, total: 24, blocked: 0, allowed: 0 })
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [agents, setAgents]     = useState<Agent[]>([])
  const [selectedAgent, setSelectedAgent] = useState<string>('default_agent')
  const [loadingAgents, setLoadingAgents] = useState(true)

  // Load available agents on mount
  useEffect(() => {
    fetch('/api/agents')
      .then(r => r.json())
      .then((data: Agent[]) => {
        setAgents(data)
        const def = data.find(a => a.is_default)
        if (def) setSelectedAgent(def.id)
      })
      .catch(() => {})
      .finally(() => setLoadingAgents(false))
  }, [])

  const startScan = async () => {
    setRunning(true)
    setEvents([])
    setProgress({ current: 0, total: 24, blocked: 0, allowed: 0 })

    try {
      const res = await fetch('/api/scan/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agentId: selectedAgent }),
      })
      const data = await res.json()
      setSessionId(data.sessionId)

      const evtSource = new EventSource(`/api/scan/stream?sessionId=${data.sessionId}`)

      evtSource.addEventListener('scan_start', (e) => {
        const payload = JSON.parse(e.data)
        setProgress(p => ({ ...p, total: payload.total_probes }))
      })

      evtSource.addEventListener('probe_result', (e) => {
        const payload = JSON.parse(e.data)
        setEvents(prev => [payload, ...prev])
        setProgress(p => ({
          ...p,
          current: p.current + 1,
          blocked: p.blocked + (payload.status === 'BLOCKED' ? 1 : 0),
          allowed: p.allowed + (payload.status === 'ALLOWED' ? 1 : 0),
        }))
      })

      evtSource.addEventListener('scan_complete', () => {
        evtSource.close()
        setRunning(false)
      })

      evtSource.onerror = () => {
        evtSource.close()
        setRunning(false)
      }
    } catch (err) {
      console.error(err)
      setRunning(false)
    }
  }

  const activeAgent = agents.find(a => a.id === selectedAgent)

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 600 }}>Live Scan</h1>
        <button
          id="start-scan-btn"
          className="btn-primary"
          onClick={startScan}
          disabled={running}
          style={{ opacity: running ? 0.5 : 1 }}
        >
          {running ? 'Scanning...' : '▶ Start Scan'}
        </button>
      </div>

      {/* Agent Selector */}
      <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
        <div style={{ marginBottom: '1rem' }}>
          <label style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.75rem' }}>
            Target Agent
          </label>

          {loadingAgents ? (
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>Loading agents…</div>
          ) : (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem' }}>
              {agents.map(agent => (
                <button
                  key={agent.id}
                  id={`agent-btn-${agent.id}`}
                  onClick={() => !running && setSelectedAgent(agent.id)}
                  disabled={running}
                  style={{
                    padding: '0.6rem 1.2rem',
                    borderRadius: '8px',
                    border: selectedAgent === agent.id
                      ? '1px solid var(--accent-blue)'
                      : '1px solid rgba(255,255,255,0.08)',
                    background: selectedAgent === agent.id
                      ? 'rgba(59,130,246,0.15)'
                      : 'rgba(255,255,255,0.03)',
                    color: selectedAgent === agent.id ? 'var(--accent-blue)' : 'var(--text-secondary)',
                    fontWeight: selectedAgent === agent.id ? 600 : 400,
                    fontSize: '0.875rem',
                    cursor: running ? 'not-allowed' : 'pointer',
                    transition: 'all 0.15s ease',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.4rem',
                  }}
                >
                  {agent.is_default && <span title="Default agent">🛡️</span>}
                  {agent.name}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Selected agent description */}
        {activeAgent && (
          <div style={{
            marginTop: '0.75rem',
            padding: '0.75rem 1rem',
            borderRadius: '8px',
            background: 'rgba(255,255,255,0.03)',
            borderLeft: '3px solid var(--accent-blue)',
            fontSize: '0.875rem',
            color: 'var(--text-secondary)',
          }}>
            <span style={{ fontWeight: 600, color: 'var(--text-primary)', marginRight: '0.5rem' }}>{activeAgent.name}</span>
            {activeAgent.description}
          </div>
        )}

        {agents.length === 0 && !loadingAgents && (
          <div style={{ color: 'var(--accent-amber)', fontSize: '0.875rem' }}>
            ⚠ No agents found in backend/agents/. Add a Python file there to get started.
          </div>
        )}
      </div>

      {/* Progress bar */}
      <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '2rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
          <span>Progress: {progress.current}/{progress.total}</span>
          <span>
            Blocked: <span style={{ color: 'var(--accent-red)' }}>{progress.blocked}</span>
            {' '}|{' '}
            Allowed: <span style={{ color: 'var(--accent-green)' }}>{progress.allowed}</span>
          </span>
        </div>
        <div style={{ width: '100%', height: '8px', background: 'rgba(255,255,255,0.1)', borderRadius: '4px', overflow: 'hidden' }}>
          <div style={{
            height: '100%',
            width: `${(progress.current / progress.total) * 100}%`,
            background: 'var(--accent-blue)',
            transition: 'width 0.3s ease',
          }} />
        </div>
      </div>

      {/* Event feed */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {events.map((evt, idx) => (
          <div key={idx} className="glass-panel" style={{ padding: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontWeight: 600, marginBottom: '0.5rem' }}>{evt.category} #{evt.index}</div>
              <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                Rule: {evt.matchedRule || 'none'}
                {evt.mismatch && <span style={{ color: 'var(--accent-amber)', marginLeft: '0.5rem' }}>⚠️ MISMATCH</span>}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div className={`badge ${evt.status === 'BLOCKED' ? 'badge-blocked' : 'badge-allowed'}`} style={{ marginBottom: '0.5rem', display: 'inline-block' }}>
                {evt.status}
              </div>
              <div style={{ fontSize: '0.875rem' }}>Risk: {evt.risk.toFixed(2)}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
