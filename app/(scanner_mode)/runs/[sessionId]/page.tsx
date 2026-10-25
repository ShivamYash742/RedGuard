"use client"
import React, { useEffect, useState, use } from 'react'
import { useRouter } from 'next/navigation'
import { benchmarkDataService, BenchmarkRun, OUTCOME_TIERS, RunReport, ReportCategory } from '@/lib/scanner_mode/data-service'
import { FileText, Download, ChevronDown, ChevronUp, ArrowLeft } from 'lucide-react'
import Link from 'next/link'

export default function RunReportPage({ params }: { params: Promise<{ sessionId: string }> }) {
  const { sessionId: routeSessionId } = use(params)
  const router = useRouter()

  const [sessions, setSessions] = useState<BenchmarkRun[]>([])
  const [report, setReport] = useState<RunReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [showPrompt, setShowPrompt] = useState(false)

  useEffect(() => {
    async function loadSessions() {
      try {
        const data = await benchmarkDataService.fetchSessions()
        setSessions(data)
      } catch (err) {
        console.error('Failed to load sessions:', err)
      } finally {
        setLoading(false)
      }
    }
    loadSessions()
  }, [])

  useEffect(() => {
    if (!routeSessionId) return
    async function loadReport() {
      try {
        const rep = await benchmarkDataService.fetchReport(routeSessionId)
        setReport(rep)
      } catch (err) {
        console.error('Failed to load report:', err)
        setReport(null)
      }
    }
    loadReport()
  }, [routeSessionId])

  if (loading) return <div className="p-8 text-center text-xs">Loading benchmark reports...</div>

  const overall = report?.reportJson?.overall
  const categoryBreakdown = report?.reportJson?.category_breakdown || []
  const currentSessionObj = sessions.find(s => s.sessionId === routeSessionId)
  const hasTiers = overall?.filtered !== undefined

  const downloadCSV = () => {
    if (!report) return
    const headers = hasTiers
      ? ['Category', 'Probes', 'Filtered', 'Refused', 'Ignored', 'Compromised', 'ModelAloneCompromised', 'HighestRiskScore']
      : ['Category', 'Probes', 'Blocked', 'Allowed', 'HighestRiskScore']
    const rows = categoryBreakdown.map((cb: ReportCategory) => hasTiers
      ? [cb.category, cb.probes, cb.filtered, cb.refused, cb.ignored, cb.allowed, cb.model_compromised, cb.highest_risk_score || 0]
      : [cb.category, cb.probes, cb.blocked, cb.allowed, cb.highest_risk_score || 0])
    const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `redguard-report-${routeSessionId}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[var(--border-subtle)] pb-4">
        <div>
          <Link href="/runs" className="inline-flex items-center gap-1 text-xs text-[var(--primary)] font-semibold hover:underline mb-2">
            <ArrowLeft className="h-3 w-3" /> Back to Runs
          </Link>
          <div className="flex items-center gap-2 text-xs font-semibold text-[var(--primary)] uppercase tracking-wider mb-1">
            <FileText className="h-4 w-4" /> Run Report
          </div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-tight">Benchmark Security Report</h1>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Empirical evaluation results, category breakdown, & threat analysis for this run.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={routeSessionId || ''}
            onChange={e => router.push(`/runs/${e.target.value}`)}
            className="rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-base)] px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] focus:outline-none focus:border-[var(--primary)]"
          >
            {sessions.map(s => (
              <option key={s.id} value={s.sessionId}>
                {s.agentName || s.sessionId} ({new Date(s.startedAt).toLocaleString()})
              </option>
            ))}
          </select>

          {report && (
            <div className="flex items-center gap-1.5">
              <a
                href={`data:text/markdown;charset=utf-8,${encodeURIComponent(report.reportMarkdown || '')}`}
                download={`redguard-report-${routeSessionId}.md`}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius)] bg-[var(--primary)] text-[var(--primary-foreground)] text-xs font-semibold hover:bg-[var(--primary-hover)] transition-colors"
              >
                <Download className="h-3.5 w-3.5" /> Markdown
              </a>
              <button
                onClick={downloadCSV}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius)] bg-[var(--surface-raised)] border border-[var(--border-default)] text-xs font-medium text-[var(--text-primary)] hover:bg-[var(--surface-base)] transition-colors"
              >
                <Download className="h-3.5 w-3.5 text-[var(--success)]" /> CSV
              </button>
            </div>
          )}
        </div>
      </div>

      {!report ? (
        <div className="research-card p-10 text-center text-xs text-[var(--text-muted)]">
          No report found for session &quot;{routeSessionId}&quot;.
        </div>
      ) : (
        <div className="space-y-6">
          {/* Target Metadata Card */}
          <div className="research-card space-y-3">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-2">
              <div>
                <span className="text-[10px] font-semibold text-[var(--primary)] uppercase tracking-wider block">
                  Evaluated Target Agent
                </span>
                <h2 className="text-xl font-extrabold text-[var(--text-primary)] mt-0.5">
                  {overall?.agent_name || currentSessionObj?.agentName || 'Default Guard'}
                </h2>
                <div className="text-xs text-[var(--text-secondary)] mt-1 font-mono">
                  Endpoint: {overall?.model_name || 'NVIDIA NIM'} | Agent ID: {overall?.agent_id || 'nemotron_3_ultra'}
                </div>
              </div>

              <div className="text-right text-xs font-mono text-[var(--text-muted)] space-y-0.5">
                <div>Session: <span className="text-[var(--text-primary)]">{overall?.session_id}</span></div>
                <div>Integrity Hash: <span className="text-[var(--primary)]">{report.manifestSha256?.substring(0, 16)}...</span></div>
              </div>
            </div>

            {overall?.system_prompt && (
              <div className="pt-3 border-t border-[var(--border-subtle)]">
                <button
                  onClick={() => setShowPrompt(!showPrompt)}
                  className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--primary)] hover:underline"
                >
                  {showPrompt ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                  {showPrompt ? 'Hide Configured System Prompt' : 'Inspect Configured System Prompt'}
                </button>

                {showPrompt && (
                  <pre className="mt-3 p-4 rounded-[var(--radius)] bg-[var(--surface-base)] border border-[var(--border-subtle)] font-mono text-xs text-[var(--text-secondary)] whitespace-pre-wrap max-h-48 overflow-y-auto">
                    {overall.system_prompt}
                  </pre>
                )}
              </div>
            )}
          </div>

          {/* 4 Executive Metric Scorecards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="research-card text-center border-t-2 border-t-[var(--success)]">
              <span className="text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider block">Security Resistance Score</span>
              <div className="text-3xl font-black text-[var(--success)] mt-2 font-mono">
                {((overall?.block_rate || 0) * 100).toFixed(1)}%
              </div>
              <span className="text-xs text-[var(--text-secondary)] mt-1 block font-mono">{overall?.blocked} / {overall?.total_probes} Resisted</span>
            </div>

            <div className="research-card text-center border-t-2 border-t-[var(--danger)]">
              <span className="text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider block">Attack Success Rate (ASR)</span>
              <div className="text-3xl font-black text-[var(--danger)] mt-2 font-mono">
                {(((overall?.allowed || 0) / (overall?.total_probes || 1)) * 100).toFixed(1)}%
              </div>
              <span className="text-xs text-[var(--text-secondary)] mt-1 block font-mono">{overall?.allowed} Compromised</span>
              {hasTiers && (
                <span className="text-[11px] text-[var(--text-muted)] mt-0.5 block font-mono">
                  Model alone (filter off): {overall.model_compromised} of {overall.model_answered ?? overall.total_probes}
                </span>
              )}
              {!!overall?.mixed_rows_model_alone && (
                <span className="text-[11px] text-[var(--warning)] mt-0.5 block font-mono" title="A refusal phrase and a success indicator both matched. Counted as refusals; compromised if success took precedence.">
                  {overall.mixed_rows_model_alone} mixed rows: ASR up to {(100 * ((overall.allowed ?? 0) + (overall.mixed_rows ?? 0)) / (overall.total_probes || 1)).toFixed(1)}%
                </span>
              )}
              {!!overall?.no_answer && (
                <span className="text-[11px] text-[var(--text-muted)] mt-0.5 block font-mono" title="The agent hit its step limit and never answered; left out of every rate">
                  No answer: {overall.no_answer} attacks, {overall.controls_no_answer ?? 0} controls
                </span>
              )}
            </div>

            <div className="research-card text-center border-t-2 border-t-[var(--primary)]">
              <span className="text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider block">Total Probes Fired</span>
              <div className="text-3xl font-black text-[var(--text-primary)] mt-2 font-mono">{overall?.total_probes || 0}</div>
              <span className="text-xs text-[var(--text-secondary)] mt-1 block">Across {benchmarkDataService.getAttackFamilies().length} Attack Families</span>
            </div>

            <div className="research-card text-center border-t-2 border-t-[var(--warning)]">
              <span className="text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider block">Intent Mismatches</span>
              <div className="text-3xl font-black text-[var(--warning)] mt-2 font-mono">{overall?.mismatches || 0}</div>
              <span className="text-xs text-[var(--text-secondary)] mt-1 block">Classifier Contradictions</span>
            </div>
          </div>

          {/* Category Breakdown Table */}
          <div className="research-card space-y-4">
            <h3 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider">
              Attack Family Category Breakdown
            </h3>

            <div className="overflow-x-auto rounded-[var(--radius)] border border-[var(--border-subtle)]">
              <table className="research-table">
                <thead>
                  <tr>
                    <th>Attack Family Category</th>
                    <th className="text-center">Probes</th>
                    {hasTiers ? (
                      OUTCOME_TIERS.map(t => <th key={t.key} className="text-center" title={t.hint}>{t.label}</th>)
                    ) : (
                      <>
                        <th className="text-center">Resisted (Secure)</th>
                        <th className="text-center">Compromised (ASR)</th>
                      </>
                    )}
                    <th className="text-center">Mismatches</th>
                    <th className="text-center">Max Risk Score</th>
                  </tr>
                </thead>
                <tbody>
                  {categoryBreakdown.map((cb: ReportCategory, idx: number) => (
                    <tr key={idx}>
                      <td className="font-bold capitalize text-xs text-[var(--text-primary)]">{cb.category.replace(/_/g, ' ')}</td>
                      <td className="font-mono text-xs text-center">{cb.probes}</td>
                      {hasTiers ? (
                        <>
                          <td className="font-mono text-xs text-center">{cb.filtered}</td>
                          <td className="font-mono text-xs text-center">{cb.refused}</td>
                          <td className="font-mono text-xs text-center">{cb.ignored}</td>
                          <td className="font-mono text-xs text-center text-[var(--danger)] font-semibold">{cb.allowed}</td>
                        </>
                      ) : (
                        <>
                          <td className="font-mono text-xs text-center text-[var(--success)] font-semibold">{cb.blocked}</td>
                          <td className="font-mono text-xs text-center text-[var(--danger)] font-semibold">{cb.allowed}</td>
                        </>
                      )}
                      <td className="font-mono text-xs text-center text-[var(--warning)]">{cb.mismatches}</td>
                      <td className="font-mono text-xs text-center font-bold">{cb.highest_risk_score ? cb.highest_risk_score.toFixed(2) : '0.00'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
