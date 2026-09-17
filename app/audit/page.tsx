"use client"
import React, { useEffect, useState } from 'react'
import { ScrollText, ChevronDown, ChevronUp } from 'lucide-react'
import { TableSkeleton } from '@/components/Skeletons'
import EmptyState from '@/components/EmptyState'

export default function AuditLog() {
  const [events, setEvents] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedRow, setExpandedRow] = useState<string | null>(null)

  useEffect(() => {
    async function loadEvents() {
      try {
        const res = await fetch('/api/events')
        if (res.ok) {
          setEvents(await res.json())
        }
      } catch (err) {
        console.error("Failed to load events", err)
      } finally {
        setLoading(false)
      }
    }
    loadEvents()
  }, [])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="border-b border-[var(--border-subtle)] pb-4">
        <div className="flex items-center gap-2 text-xs font-semibold text-[var(--primary)] uppercase tracking-wider mb-1">
          <ScrollText className="h-4 w-4" /> Inspector Trail
        </div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-tight">Audit Log</h1>
        <p className="text-xs text-[var(--text-secondary)] mt-0.5">
          Rule-based and classifier verdicts recorded by the proxy inspector for every intercepted request.
        </p>
      </div>

      {loading ? (
        <TableSkeleton rows={6} />
      ) : events.length === 0 ? (
        <EmptyState
          title="No audit events recorded"
          description="Inspector events appear here once traffic passes through the proxy inspect middleware."
          icon="inbox"
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-raised)]">
          <table className="research-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Category</th>
                <th>Status</th>
                <th>Risk Score</th>
                <th>ML Verdict</th>
                <th>Rule</th>
                <th className="text-center">Details</th>
              </tr>
            </thead>
            <tbody>
              {events.map((evt) => {
                const isExpanded = expandedRow === evt.id
                return (
                  <React.Fragment key={evt.id}>
                    <tr
                      onClick={() => setExpandedRow(isExpanded ? null : evt.id)}
                      className="cursor-pointer hover:bg-[var(--surface-base)] transition-colors"
                    >
                      <td className="text-xs text-[var(--text-secondary)]">{new Date(evt.timestamp).toLocaleString()}</td>
                      <td className="text-xs font-medium capitalize text-[var(--text-primary)]">{evt.category}</td>
                      <td>
                        <span className={`badge-semantic ${evt.status === 'BLOCKED' ? 'badge-success' : 'badge-danger'}`}>
                          {evt.status}
                        </span>
                      </td>
                      <td className="font-mono text-xs font-semibold text-[var(--text-primary)]">{evt.regexRiskScore.toFixed(2)}</td>
                      <td className="text-xs text-[var(--text-secondary)]">{evt.classifierVerdict || 'N/A'}</td>
                      <td className="font-mono text-xs text-[var(--text-muted)]">{evt.matchedRule || '-'}</td>
                      <td className="text-center text-[var(--text-muted)]">
                        {isExpanded ? <ChevronUp className="h-3.5 w-3.5 inline" /> : <ChevronDown className="h-3.5 w-3.5 inline" />}
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr>
                        <td colSpan={7} className="bg-[var(--surface-base)] p-4">
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                              <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)] mb-2">Prompt</h4>
                              <pre className="whitespace-pre-wrap break-words font-mono text-xs bg-[var(--surface-raised)] border border-[var(--border-subtle)] p-3 rounded-lg text-[var(--text-primary)]">
                                {evt.promptText}
                              </pre>
                            </div>
                            <div>
                              <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)] mb-2">Analysis Details</h4>
                              <div className="bg-[var(--surface-raised)] border border-[var(--border-subtle)] p-3 rounded-lg text-xs space-y-1.5">
                                <div><span className="text-[var(--text-muted)]">Declared Intent:</span> <span className="text-[var(--text-primary)] font-medium">{evt.declaredIntent}</span></div>
                                <div><span className="text-[var(--text-muted)]">Detected Intent:</span> <span className="text-[var(--text-primary)] font-medium">{evt.detectedIntent}</span></div>
                                <div><span className="text-[var(--text-muted)]">Mismatch:</span> <span className={evt.mismatch ? 'text-[var(--danger)] font-semibold' : 'text-[var(--text-primary)] font-medium'}>{evt.mismatch ? 'Yes' : 'No'}</span></div>
                                <div><span className="text-[var(--text-muted)]">ML Score:</span> <span className="text-[var(--text-primary)] font-medium">{evt.classifierScore ? evt.classifierScore.toFixed(4) : 'N/A'}</span></div>
                                <div><span className="text-[var(--text-muted)]">Event Hash:</span> <span className="font-mono text-[var(--text-primary)]">{evt.eventHash.substring(0, 16)}...</span></div>
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
