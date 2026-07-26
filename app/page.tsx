"use client"
import { useEffect, useState } from 'react'
import StatCard from '@/components/StatCard'
import Link from 'next/link'

export default function Dashboard() {
  const [stats, setStats] = useState<any>(null)
  const [sessions, setSessions] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function loadData() {
      try {
        const [statsRes, sessionsRes] = await Promise.all([
          fetch('/api/stats'),
          fetch('/api/sessions')
        ])
        if (statsRes.ok) setStats(await statsRes.json())
        if (sessionsRes.ok) setSessions(await sessionsRes.json())
      } catch (err) {
        console.error("Failed to load dashboard data", err)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [])

  if (loading) return <div>Loading dashboard...</div>

  return (
    <div>
      <h1 style={{ marginBottom: '2rem', fontSize: '2rem', fontWeight: 600 }}>Overview</h1>
      
      <div className="grid-4">
        <StatCard label="Total Scans" value={stats?.totalSessions || 0} />
        <StatCard label="Probes Fired" value={stats?.totalProbes || 0} />
        <StatCard label="Blocked (Regex)" value={stats?.totalBlocked || 0} />
        <StatCard label="Coverage Gap" value={stats?.coverageGap || 0} />
      </div>

      <div style={{ marginTop: '3rem' }}>
        <h2 style={{ marginBottom: '1.5rem', fontSize: '1.25rem', fontWeight: 600 }}>Recent Sessions</h2>
        <div className="glass-panel" style={{ padding: '1.5rem' }}>
          {sessions.length === 0 ? (
            <p>No sessions found. Run a scan to see data.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Session ID</th>
                  <th>Date</th>
                  <th>Probes</th>
                  <th>Blocked</th>
                  <th>Allowed</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {sessions.slice(0, 5).map(s => (
                  <tr key={s.id}>
                    <td style={{ fontFamily: 'monospace' }}>{s.sessionId}</td>
                    <td>{new Date(s.startedAt).toLocaleString()}</td>
                    <td>{s.totalProbes}</td>
                    <td>{s.blocked}</td>
                    <td>{s.allowed}</td>
                    <td>
                      <span className={`badge ${s.status === 'COMPLETED' ? 'badge-allowed' : 'badge-blocked'}`}>
                        {s.status}
                      </span>
                    </td>
                    <td>
                      <Link href={`/reports?session=${s.sessionId}`} style={{ color: 'var(--accent-blue)', textDecoration: 'none' }}>
                        View Report
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
