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
  const [showPrompt, setShowPrompt] = useState(false)

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

  if (loading) return <div style={{ padding: '2rem', color: 'var(--text-secondary)' }}>Loading benchmark evaluation reports...</div>

  const overall = report?.reportJson?.overall
  const categoryBreakdown = report?.reportJson?.category_breakdown || []
  const highRiskAllowed = report?.reportJson?.high_risk_allowed || []
  const currentSessionObj = sessions.find(s => s.sessionId === selectedSession)

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: 600 }}>Benchmark Security Report</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginTop: '0.25rem' }}>
            Comprehensive vulnerability & resistance assessment per LLM agent architecture
          </p>
        </div>

        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <select 
            value={selectedSession || ''} 
            onChange={e => setSelectedSession(e.target.value)}
            style={{ 
              padding: '0.75rem 1rem', 
              borderRadius: '8px', 
              background: 'var(--panel-bg)', 
              color: 'var(--text-primary)',
              border: '1px solid var(--panel-border)',
              fontSize: '0.875rem',
              outline: 'none',
              cursor: 'pointer'
            }}
          >
            {sessions.map(s => (
              <option key={s.id} value={s.sessionId}>
                {s.agentName || s.sessionId} ({new Date(s.startedAt).toLocaleString()})
              </option>
            ))}
          </select>

          {report && (
            <a 
              href={`data:text/markdown;charset=utf-8,${encodeURIComponent(report.reportMarkdown)}`} 
              download={`redguard-report-${selectedSession}.md`}
              className="btn-primary"
              style={{ textDecoration: 'none', whiteSpace: 'nowrap' }}
            >
              📥 Download Report (.md)
            </a>
          )}
        </div>
      </div>

      {!report ? (
        <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
          No evaluation report found for this session yet. Run a benchmark evaluation to generate data.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          
          {/* Target Agent & Model Metadata Card */}
          <div className="glass-panel" style={{ padding: '1.5rem', borderLeft: '4px solid var(--accent-blue)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.25rem' }}>
              <div>
                <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--accent-blue)', display: 'block', marginBottom: '0.35rem' }}>
                  Target AI Agent Under Evaluation
                </span>
                <h2 style={{ fontSize: '1.5rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                  {overall?.agent_name || currentSessionObj?.agentName || 'Default Agent'}
                </h2>
                <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                  Model Endpoint: <code style={{ color: 'var(--text-primary)', background: 'rgba(255,255,255,0.06)', padding: '0.2rem 0.5rem', borderRadius: '4px', fontFamily: 'monospace' }}>{overall?.model_name || 'NVIDIA NIM'}</code>
                  {' '}| Agent ID: <code style={{ color: 'var(--text-secondary)', fontFamily: 'monospace' }}>{overall?.agent_id || currentSessionObj?.agentId || 'nemotron_3_ultra'}</code>
                </div>
              </div>

              <div style={{ textAlign: 'right', fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                <div>Session: <span style={{ fontFamily: 'monospace', color: 'var(--text-primary)' }}>{overall?.session_id}</span></div>
                <div>Evaluated: {new Date(report.generatedAt).toLocaleString()}</div>
                <div>Integrity Hash: <span style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{report.manifestSha256.substring(0, 12)}...</span></div>
              </div>
            </div>

            {/* System Prompt Drawer */}
            {overall?.system_prompt && (
              <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
                <button
                  onClick={() => setShowPrompt(!showPrompt)}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: 'var(--accent-blue)',
                    fontSize: '0.85rem',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.4rem',
                    padding: 0
                  }}
                >
                  {showPrompt ? '▼ Hide Configured System Prompt' : '▶ View Configured System Prompt'}
                </button>
                {showPrompt && (
                  <pre style={{
                    marginTop: '0.75rem',
                    padding: '1rem',
                    borderRadius: '6px',
                    background: 'rgba(0,0,0,0.4)',
                    border: '1px solid rgba(255,255,255,0.06)',
                    color: 'var(--text-secondary)',
                    fontFamily: 'monospace',
                    fontSize: '0.8rem',
                    whiteSpace: 'pre-wrap',
                    maxHeight: '250px',
                    overflowY: 'auto'
                  }}>
                    {overall.system_prompt}
                  </pre>
                )}
              </div>
            )}
          </div>

          {/* Executive Security Summary Metrics Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.5rem' }}>
            
            <div className="glass-panel" style={{ padding: '1.5rem', textAlign: 'center', borderTop: '3px solid var(--accent-green)' }}>
              <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                Security Resistance Score
              </div>
              <div style={{ fontSize: '2.25rem', fontWeight: 700, color: 'var(--accent-green)' }}>
                {((overall?.block_rate || 0) * 100).toFixed(1)}%
              </div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.35rem' }}>
                {overall?.blocked} / {overall?.total_probes} Attacks Resisted
              </div>
            </div>

            <div className="glass-panel" style={{ padding: '1.5rem', textAlign: 'center', borderTop: '3px solid var(--accent-red)' }}>
              <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                Attack Success Rate (ASR)
              </div>
              <div style={{ fontSize: '2.25rem', fontWeight: 700, color: 'var(--accent-red)' }}>
                {(((overall?.allowed || 0) / (overall?.total_probes || 1)) * 100).toFixed(1)}%
              </div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.35rem' }}>
                {overall?.allowed} Compromised Gaps
              </div>
            </div>

            <div className="glass-panel" style={{ padding: '1.5rem', textAlign: 'center', borderTop: '3px solid var(--accent-blue)' }}>
              <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                Total Probes Fired
              </div>
              <div style={{ fontSize: '2.25rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                {overall?.total_probes || 0}
              </div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.35rem' }}>
                Across 8 Attack Families
              </div>
            </div>

            <div className="glass-panel" style={{ padding: '1.5rem', textAlign: 'center', borderTop: '3px solid var(--accent-amber)' }}>
              <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                Intent Mismatches
              </div>
              <div style={{ fontSize: '2.25rem', fontWeight: 700, color: 'var(--accent-amber)' }}>
                {overall?.mismatches || 0}
              </div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.35rem' }}>
                DPI vs ML Classifier Contradictions
              </div>
            </div>

          </div>

          {/* Attack Category Breakdown Table */}
          <div className="glass-panel" style={{ padding: '1.5rem' }}>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '1.25rem', color: 'var(--text-primary)' }}>
              Attack Category Breakdown
            </h3>

            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Attack Family Category</th>
                    <th style={{ textAlign: 'center' }}>Probes</th>
                    <th style={{ textAlign: 'center' }}>Resisted (Blocked)</th>
                    <th style={{ textAlign: 'center' }}>Compromised (Allowed)</th>
                    <th style={{ textAlign: 'center' }}>Mismatches</th>
                    <th style={{ textAlign: 'center' }}>Max Risk Score</th>
                  </tr>
                </thead>
                <tbody>
                  {categoryBreakdown.map((cb: any, idx: number) => (
                    <tr key={idx}>
                      <td style={{ fontWeight: 600 }}>{cb.category.replace(/_/g, ' ')}</td>
                      <td style={{ textAlign: 'center' }}>{cb.probes}</td>
                      <td style={{ textAlign: 'center', color: cb.blocked > 0 ? 'var(--accent-green)' : 'inherit', fontWeight: cb.blocked > 0 ? 600 : 400 }}>
                        {cb.blocked}
                      </td>
                      <td style={{ textAlign: 'center', color: cb.allowed > 0 ? 'var(--accent-red)' : 'inherit', fontWeight: cb.allowed > 0 ? 600 : 400 }}>
                        {cb.allowed}
                      </td>
                      <td style={{ textAlign: 'center', color: cb.mismatches > 0 ? 'var(--accent-amber)' : 'inherit' }}>
                        {cb.mismatches}
                      </td>
                      <td style={{ textAlign: 'center', fontFamily: 'monospace' }}>
                        {cb.highest_risk_score ? cb.highest_risk_score.toFixed(2) : '0.00'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Vulnerability Analysis / High Risk Allowed Section */}
          <div className="glass-panel" style={{ padding: '1.5rem' }}>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '1rem', color: 'var(--accent-red)' }}>
              Vulnerability Analysis (Compromised Attacks)
            </h3>

            {highRiskAllowed.length === 0 ? (
              <div style={{ color: 'var(--accent-green)', padding: '1rem', background: 'rgba(34, 197, 94, 0.08)', borderRadius: '6px', borderLeft: '4px solid var(--accent-green)', fontSize: '0.9rem' }}>
                ✅ Outstanding Security: No high-risk compromised attacks were recorded for this evaluation run.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {highRiskAllowed.map((item: any, idx: number) => (
                  <div key={idx} style={{ background: 'rgba(239, 68, 68, 0.08)', padding: '1rem', borderRadius: '8px', borderLeft: '4px solid var(--accent-red)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
                    <div>
                      <span style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '0.95rem' }}>{item.category.replace(/_/g, ' ')}</span>
                      <span style={{ marginLeft: '0.75rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                        Risk Score: <strong>{item.risk_score ? item.risk_score.toFixed(2) : 'N/A'}</strong> | ML Verdict: <strong style={{ color: item.classifier_verdict === 'ADVERSARIAL' ? 'var(--accent-red)' : 'var(--text-primary)' }}>{item.classifier_verdict || 'N/A'}</strong>
                      </span>
                    </div>
                    <span style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: 'var(--text-secondary)', background: 'rgba(0,0,0,0.3)', padding: '0.2rem 0.5rem', borderRadius: '4px' }}>
                      Hash: {item.event_hash ? item.event_hash.substring(0, 12) : 'N/A'}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

        </div>
      )}
    </div>
  )
}

export default function Reports() {
  return (
    <Suspense fallback={<div style={{ padding: '2rem' }}>Loading report...</div>}>
      <ReportsContent />
    </Suspense>
  )
}
