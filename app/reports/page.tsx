"use client"
import { useEffect, useState, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'

function ReportsContent() {
  const searchParams = useSearchParams()
  const initialSession = searchParams.get('session')
  
  const [sessions, setSessions] = useState<any[]>([])
  const [selectedSession, setSelectedSession] = useState<string | null>(initialSession)
  const [report, setReport] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function loadSessions() {
      try {
        const res = await fetch('/api/sessions')
        if (res.ok) {
          const data = await res.json()
          setSessions(data)
          if (!selectedSession && data.length > 0) {
            setSelectedSession(data[0].sessionId)
          }
        }
      } catch (err) {
        console.error("Failed to load sessions", err)
      } finally {
        setLoading(false)
      }
    }
    loadSessions()
  }, [])

  useEffect(() => {
    if (!selectedSession) return
    async function loadReport() {
      try {
        const res = await fetch(`/api/reports/${selectedSession}`)
        if (res.ok) {
          setReport(await res.json())
        } else {
          setReport(null)
        }
      } catch (err) {
        console.error("Failed to load report", err)
        setReport(null)
      }
    }
    loadReport()
  }, [selectedSession])

  if (loading) return <div>Loading...</div>

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 600 }}>Security Reports</h1>
        <select 
          value={selectedSession || ''} 
          onChange={e => setSelectedSession(e.target.value)}
          style={{ 
            padding: '0.75rem', 
            borderRadius: '8px', 
            background: 'var(--panel-bg)', 
            color: 'var(--text-primary)',
            border: '1px solid var(--panel-border)'
          }}
        >
          {sessions.map(s => (
            <option key={s.id} value={s.sessionId}>{s.sessionId} ({new Date(s.startedAt).toLocaleString()})</option>
          ))}
        </select>
      </div>

      {!report ? (
        <div className="glass-panel" style={{ padding: '2rem', textAlign: 'center' }}>
          No report generated for this session yet.
        </div>
      ) : (
        <div className="glass-panel" style={{ padding: '2rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2rem', borderBottom: '1px solid var(--panel-border)', paddingBottom: '1rem' }}>
            <div>
              <h2 style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>Audit Report</h2>
              <div style={{ color: 'var(--text-secondary)' }}>Generated: {new Date(report.generatedAt).toLocaleString()}</div>
            </div>
            <div>
              <a 
                href={`data:text/markdown;charset=utf-8,${encodeURIComponent(report.reportMarkdown)}`} 
                download={`report-${selectedSession}.md`}
                className="btn-primary"
                style={{ textDecoration: 'none' }}
              >
                Download Markdown
              </a>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem', marginBottom: '2rem' }}>
            <div>
              <h3 style={{ marginBottom: '1rem', color: 'var(--accent-blue)' }}>Executive Summary</h3>
              <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <li><strong>Total Probes Fired:</strong> {report.reportJson.overall.total_probes}</li>
                <li><strong>Blocked:</strong> <span style={{ color: 'var(--accent-red)'}}>{report.reportJson.overall.blocked}</span></li>
                <li><strong>Allowed (Gap):</strong> <span style={{ color: 'var(--accent-green)'}}>{report.reportJson.overall.allowed}</span></li>
                <li><strong>Block Rate:</strong> {(report.reportJson.overall.block_rate * 100).toFixed(1)}%</li>
                <li><strong>Mismatches:</strong> <span style={{ color: 'var(--accent-amber)'}}>{report.reportJson.overall.mismatches}</span></li>
              </ul>
            </div>
            <div>
              <h3 style={{ marginBottom: '1rem', color: 'var(--accent-blue)' }}>Metadata</h3>
              <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.875rem' }}>
                <li><strong>Session ID:</strong> {report.reportJson.overall.session_id}</li>
                <li><strong>Report SHA256:</strong> <span style={{ fontFamily: 'monospace' }}>{report.manifestSha256.substring(0, 16)}...</span></li>
              </ul>
            </div>
          </div>

          <h3 style={{ marginBottom: '1rem', color: 'var(--accent-blue)' }}>Category Breakdown</h3>
          <table className="data-table" style={{ marginBottom: '2rem' }}>
            <thead>
              <tr>
                <th>Category</th>
                <th>Probes</th>
                <th>Blocked</th>
                <th>Allowed</th>
                <th>Mismatch</th>
                <th>Max Risk</th>
              </tr>
            </thead>
            <tbody>
              {report.reportJson.category_breakdown.map((cb: any, idx: number) => (
                <tr key={idx}>
                  <td>{cb.category}</td>
                  <td>{cb.probes}</td>
                  <td style={{ color: cb.blocked > 0 ? 'var(--accent-red)' : 'inherit' }}>{cb.blocked}</td>
                  <td style={{ color: cb.allowed > 0 ? 'var(--accent-green)' : 'inherit' }}>{cb.allowed}</td>
                  <td style={{ color: cb.mismatches > 0 ? 'var(--accent-amber)' : 'inherit' }}>{cb.mismatches}</td>
                  <td>{cb.highest_risk_score.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          
          <h3 style={{ marginBottom: '1rem', color: 'var(--accent-blue)' }}>Coverage Gaps (High Risk Allowed)</h3>
          {report.reportJson.high_risk_allowed.length === 0 ? (
            <p style={{ color: 'var(--text-secondary)' }}>No high risk prompts were allowed through.</p>
          ) : (
            <ul style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {report.reportJson.high_risk_allowed.map((item: any, idx: number) => (
                <li key={idx} style={{ background: 'rgba(239, 68, 68, 0.1)', padding: '0.75rem', borderRadius: '4px', borderLeft: '4px solid var(--accent-red)' }}>
                  <strong>{item.category}</strong> - Risk: {item.risk_score.toFixed(2)} | ML Verdict: {item.classifier_verdict} 
                  <span style={{ float: 'right', fontFamily: 'monospace', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{item.event_hash.substring(0, 12)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

export default function Reports() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <ReportsContent />
    </Suspense>
  )
}
