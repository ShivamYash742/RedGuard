"use client"
import { useState, useEffect } from 'react'
import Link from 'next/link'

interface Agent {
  id: string
  name: string
  description: string
  is_default: boolean
}

interface FamilyProgress {
  name: string
  total: number
  current: number
  blocked: number
  allowed: number
}

export default function LiveScan() {
  const [running, setRunning]   = useState(false)
  const [families, setFamilies] = useState<FamilyProgress[]>([])
  const [progress, setProgress] = useState({ current: 0, total: 0, blocked: 0, allowed: 0 })
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [agents, setAgents]     = useState<Agent[]>([])
  const [selectedAgent, setSelectedAgent] = useState<string>('default_agent')
  const [loadingAgents, setLoadingAgents] = useState(true)

  // Load available agents and probe count on mount
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

    fetch('/api/probes/count')
      .then(r => r.json())
      .then(data => {
        setProgress(p => ({ ...p, total: data.total }))
      })
      .catch(() => {})
  }, [])

  const startScan = async () => {
    setRunning(true)
    setFamilies([])
    setProgress(p => ({ ...p, current: 0, blocked: 0, allowed: 0 }))
    setSessionId(null)

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
        if (payload.families) {
          const fams = Object.entries(payload.families).map(([name, total]) => ({
            name,
            total: total as number,
            current: 0,
            blocked: 0,
            allowed: 0
          }))
          setFamilies(fams)
        }
      })

      evtSource.addEventListener('probe_result', (e) => {
        const payload = JSON.parse(e.data)
        
        setProgress(p => ({
          ...p,
          current: p.current + 1,
          blocked: p.blocked + (payload.status === 'BLOCKED' ? 1 : 0),
          allowed: p.allowed + (payload.status === 'ALLOWED' ? 1 : 0),
        }))

        setFamilies(prev => prev.map(f => {
          if (f.name === payload.category) {
            return {
              ...f,
              current: f.current + 1,
              blocked: f.blocked + (payload.status === 'BLOCKED' ? 1 : 0),
              allowed: f.allowed + (payload.status === 'ALLOWED' ? 1 : 0),
            }
          }
          return f
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
  const isComplete = !running && sessionId && progress.current > 0 && progress.current === progress.total

  return (
    <div>
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes pulseBorder {
          0% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.4); border-color: rgba(59, 130, 246, 0.8); }
          70% { box-shadow: 0 0 0 10px rgba(59, 130, 246, 0); border-color: rgba(59, 130, 246, 0.3); }
          100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0); border-color: rgba(59, 130, 246, 0.8); }
        }
        .active-family-card {
          animation: pulseBorder 2s infinite;
          background: rgba(59, 130, 246, 0.05) !important;
        }
      `}} />

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 600 }}>Run Benchmark Evaluation</h1>
        <div style={{ display: 'flex', gap: '1rem' }}>
          {isComplete && (
            <Link href={`/reports?session=${sessionId}`}>
              <button className="btn-primary" style={{ background: 'var(--accent-green)', color: '#fff' }}>
                📄 View Benchmark Report
              </button>
            </Link>
          )}
          <button
            id="start-scan-btn"
            className="btn-primary"
            onClick={startScan}
            disabled={running}
            style={{ opacity: running ? 0.5 : 1 }}
          >
            {running ? 'Evaluating...' : '▶ Start Evaluation'}
          </button>
        </div>
      </div>

      {/* Agent Selector */}
      <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
        <div style={{ marginBottom: '1rem' }}>
          <label style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.75rem' }}>
            Target LLM Agent
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
          <span>Overall Progress: {progress.current}/{progress.total}</span>
          <span>
            Secure (Resisted): <span style={{ color: 'var(--accent-green)' }}>{progress.blocked}</span>
            {' '}|{' '}
            Compromised: <span style={{ color: 'var(--accent-red)' }}>{progress.allowed}</span>
          </span>
        </div>
        <div style={{ width: '100%', height: '8px', background: 'rgba(255,255,255,0.1)', borderRadius: '4px', overflow: 'hidden' }}>
          <div style={{
            height: '100%',
            width: `${progress.total > 0 ? (progress.current / progress.total) * 100 : 0}%`,
            background: 'var(--accent-blue)',
            transition: 'width 0.3s ease',
          }} />
        </div>
      </div>

      {/* Families Grid */}
      {families.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1.5rem' }}>
          {families.map((f, idx) => {
            const isFinished = f.current === f.total;
            const isPending = f.current === 0;
            let isActive = false;
            if (running) {
              isActive = (f.current > 0 && f.current < f.total);
              if (!isActive && isPending) {
                // Determine if this family is next in line
                if (idx === 0 || families[idx - 1].current === families[idx - 1].total) {
                  isActive = true;
                }
              }
            }

            return (
              <div 
                key={idx} 
                className={`glass-panel ${isActive ? 'active-family-card' : ''}`} 
                style={{ 
                  padding: '1.5rem', 
                  border: isActive ? '1px solid var(--accent-blue)' : undefined,
                  opacity: isPending && !isActive ? 0.5 : 1,
                  transition: 'all 0.3s ease'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.75rem', alignItems: 'center' }}>
                  <div style={{ fontWeight: 600, fontSize: '1rem' }}>{f.name.replace(/_/g, ' ')}</div>
                  <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>{f.current} / {f.total}</div>
                </div>
                <div style={{ width: '100%', height: '6px', background: 'rgba(255,255,255,0.1)', borderRadius: '3px', overflow: 'hidden', marginBottom: '1rem' }}>
                  <div style={{
                    height: '100%',
                    width: `${f.total > 0 ? (f.current / f.total) * 100 : 0}%`,
                    background: isFinished ? 'var(--accent-green)' : 'var(--accent-blue)',
                    transition: 'width 0.3s ease, background 0.3s ease',
                  }} />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.875rem' }}>
                  <span style={{ color: 'var(--accent-green)' }}>Resisted: {f.blocked}</span>
                  <span style={{ color: 'var(--accent-red)' }}>Compromised: {f.allowed}</span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
