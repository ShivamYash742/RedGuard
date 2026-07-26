"use client"
import { useState, useEffect } from 'react'

export default function LiveScan() {
  const [running, setRunning] = useState(false)
  const [events, setEvents] = useState<any[]>([])
  const [progress, setProgress] = useState({ current: 0, total: 24, blocked: 0, allowed: 0 })
  const [sessionId, setSessionId] = useState<string | null>(null)

  const startScan = async () => {
    setRunning(true)
    setEvents([])
    setProgress({ current: 0, total: 24, blocked: 0, allowed: 0 })

    try {
      const res = await fetch('/api/scan/start', { method: 'POST' })
      const data = await res.json()
      setSessionId(data.sessionId)

      const evtSource = new EventSource(`/api/scan/stream?sessionId=${data.sessionId}`)
      
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

      evtSource.addEventListener('scan_complete', (e) => {
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

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 600 }}>Live Scan</h1>
        <button 
          className="btn-primary" 
          onClick={startScan} 
          disabled={running}
          style={{ opacity: running ? 0.5 : 1 }}
        >
          {running ? 'Scanning...' : '▶ Start Scan'}
        </button>
      </div>

      <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '2rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
          <span>Progress: {progress.current}/{progress.total}</span>
          <span>Blocked: <span style={{ color: 'var(--accent-red)'}}>{progress.blocked}</span> | Allowed: <span style={{ color: 'var(--accent-green)'}}>{progress.allowed}</span></span>
        </div>
        <div style={{ width: '100%', height: '8px', background: 'rgba(255,255,255,0.1)', borderRadius: '4px', overflow: 'hidden' }}>
          <div style={{ 
            height: '100%', 
            width: `${(progress.current / progress.total) * 100}%`, 
            background: 'var(--accent-blue)',
            transition: 'width 0.3s ease'
          }}></div>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {events.map((evt, idx) => (
          <div key={idx} className="glass-panel" style={{ padding: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontWeight: 600, marginBottom: '0.5rem' }}>{evt.category} #{evt.index}</div>
              <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                Rule: {evt.matchedRule || 'none'} {evt.mismatch && <span style={{ color: 'var(--accent-amber)', marginLeft: '0.5rem' }}>⚠️ MISMATCH</span>}
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
