"use client"
import React, { use, useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, BarChart2, AlertTriangle, ShieldCheck } from 'lucide-react'
import {
  labService, Experiment, ExperimentMetrics, OBJECTIVE_STYLES, RunSummary,
  formatCI, formatRate,
} from '@/lib/lab-service'

export default function LabExperimentPage({
  params,
}: {
  params: Promise<{ experimentId: string }>
}) {
  const { experimentId } = use(params)

  const [experiment, setExperiment] = useState<Experiment | null>(null)
  const [metrics, setMetrics] = useState<ExperimentMetrics | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      labService.fetchExperiment(experimentId),
      labService.fetchMetrics(experimentId).catch(() => null),
    ])
      .then(([exp, met]) => {
        setExperiment(exp)
        setMetrics(met)
      })
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false))
  }, [experimentId])

  if (loading) return <div className="p-8 text-center text-xs text-[var(--text-muted)]">Loading experiment…</div>

  if (error || !experiment) {
    return (
      <div className="space-y-4">
        <Link href="/lab" className="inline-flex items-center gap-1 text-xs text-[var(--primary)] font-semibold hover:underline">
          <ArrowLeft className="h-3 w-3" /> Back to Lab
        </Link>
        <div className="flex items-start gap-2 p-3 rounded-[var(--radius)] border border-[var(--danger)]/30 bg-[var(--danger-bg)] text-xs text-[var(--danger)]">
          <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
          <span className="font-mono break-all">{error ?? 'Experiment not found'}</span>
        </div>
      </div>
    )
  }

  const runs = experiment.runs ?? []
  const versions = experiment.versions?.versions ?? {}
  const aggregate = metrics?.aggregate

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="border-b border-[var(--border-subtle)] pb-4">
        <Link href="/lab" className="inline-flex items-center gap-1 text-xs text-[var(--primary)] font-semibold hover:underline mb-2">
          <ArrowLeft className="h-3 w-3" /> Back to Lab
        </Link>
        <div className="flex items-center gap-2 text-xs font-semibold text-[var(--primary)] uppercase tracking-wider mb-1">
          <BarChart2 className="h-4 w-4" /> Experiment
        </div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-tight">{experiment.name}</h1>
        <p className="text-xs text-[var(--text-secondary)] mt-0.5 font-mono">
          arm {experiment.arm} · {runs.length} runs ·{' '}
          {Object.entries(experiment.status_counts ?? {}).map(([s, n]) => `${n} ${s}`).join(' · ')}
        </p>
      </div>

      {/* Reproducibility stamp (§17) */}
      <section className="rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)] p-4">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
          Reproducibility
        </div>
        <div className="grid gap-x-6 gap-y-1 text-[10px] font-mono text-[var(--text-secondary)] sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(versions).map(([key, value]) => (
            <div key={key} className="flex justify-between gap-2">
              <span className="text-[var(--text-muted)]">{key}</span>
              <span className="text-[var(--text-primary)]">{String(value)}</span>
            </div>
          ))}
          <div className="flex justify-between gap-2">
            <span className="text-[var(--text-muted)]">git_commit</span>
            <span className="text-[var(--text-primary)] truncate">
              {String(experiment.versions?.git_commit ?? '—').slice(0, 12)}
            </span>
          </div>
          <div className="flex justify-between gap-2">
            <span className="text-[var(--text-muted)]">git_clean</span>
            {/* A dirty tree means the result cannot be reconstructed from its
                commit. Recorded, not assumed. */}
            <span className={experiment.versions?.git_clean ? 'text-[var(--success)]' : 'text-[var(--warning)]'}>
              {String(experiment.versions?.git_clean ?? 'unknown')}
            </span>
          </div>
        </div>
      </section>

      {metrics && metrics.n_failed_pairs > 0 && (
        <div className="flex items-start gap-2 p-3 rounded-[var(--radius)] border border-[var(--warning)]/30 bg-[var(--warning-bg)] text-xs text-[var(--warning)]">
          <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
          <span>
            {metrics.n_failed_pairs} pair(s) excluded from every rate below — a run hit a harness error or was
            interrupted. Run the experiment again to resume them.
          </span>
        </div>
      )}

      {/* Aggregate metrics */}
      {aggregate && metrics && (
        <section className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              label="Initial compromise (ICR)"
              value={formatRate(aggregate.icr.value)}
              sub={`n=${aggregate.icr.n} ${formatCI(aggregate.icr.ci)}`}
            />
            <MetricCard
              label="Attack success (ASR)"
              value={formatRate(aggregate.asr.value)}
              sub={`n=${aggregate.asr.n} ${formatCI(aggregate.asr.ci)}`}
            />
            <MetricCard
              label="Conditional propagation (CPR)"
              value={formatRate(aggregate.cpr)}
              sub={
                aggregate.cpr === 'n/a'
                  ? 'denominator empty — undefined, not 0%'
                  : `D=${aggregate.cpr_denominator_size}`
              }
              muted={aggregate.cpr === 'n/a'}
            />
            <MetricCard
              label="Containment rate"
              value={formatRate(aggregate.containment_rate)}
              sub={
                aggregate.mean_coverage === null
                  ? 'no propagating runs'
                  : `mean coverage ${formatRate(aggregate.mean_coverage)}`
              }
            />
          </div>

          {aggregate.containment_histogram.length > 0 && (
            <div className="rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)] p-4">
              <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-3">
                <ShieldCheck className="h-3 w-3" /> Where containment happened
              </div>
              <div className="space-y-1.5">
                {aggregate.containment_histogram.map((entry) => (
                  <div key={`${entry.agent}-${entry.mechanism}`} className="flex items-center gap-2 text-xs">
                    <span className="font-mono font-bold text-[var(--text-primary)] w-8">{entry.agent ?? '—'}</span>
                    <span className="font-mono text-[10px] text-[var(--text-secondary)] flex-1">{entry.mechanism}</span>
                    <span className="font-mono text-[10px] text-[var(--text-muted)]">{entry.count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Per case */}
          <div className="rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)] overflow-hidden">
            <div className="px-4 py-2.5 border-b border-[var(--border-subtle)] text-xs font-semibold text-[var(--text-primary)]">
              Per case
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="bg-[var(--surface-base)] text-[10px] uppercase tracking-wider text-[var(--text-muted)]">
                  <tr>
                    <th className="px-4 py-2 text-left font-semibold">Case</th>
                    <th className="px-2 py-2 text-right font-semibold">N</th>
                    <th className="px-2 py-2 text-right font-semibold">ICR</th>
                    <th className="px-2 py-2 text-right font-semibold">ASR</th>
                    <th className="px-2 py-2 text-right font-semibold">CPR</th>
                    <th className="px-2 py-2 text-right font-semibold">SOC</th>
                    <th className="px-2 py-2 text-right font-semibold">TDS vs null</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-subtle)]">
                  {Object.entries(metrics.per_case).map(([caseId, stats]) => {
                    const drift = metrics.trajectory_drift[caseId]
                    return (
                      <tr key={caseId} className="hover:bg-[var(--surface-base)]">
                        <td className="px-4 py-2 font-mono font-semibold text-[var(--text-primary)]">{caseId}</td>
                        <td className="px-2 py-2 text-right font-mono text-[var(--text-secondary)]">{stats.n}</td>
                        <td className="px-2 py-2 text-right font-mono text-[var(--text-secondary)]">{formatRate(stats.icr)}</td>
                        <td className="px-2 py-2 text-right font-mono text-[var(--text-secondary)]">{formatRate(stats.asr)}</td>
                        <td className="px-2 py-2 text-right font-mono text-[var(--text-secondary)]">{formatRate(stats.cpr)}</td>
                        <td className="px-2 py-2 text-right font-mono text-[var(--text-secondary)]">
                          {/* Needs N>=3 repetitions; below that it is not reported. */}
                          {stats.soc === null ? <span className="text-[var(--text-muted)]">N&lt;3</span> : stats.soc.toFixed(2)}
                        </td>
                        <td className="px-2 py-2 text-right font-mono text-[10px]">
                          {!drift || !drift.interpretable ? (
                            <span className="text-[var(--text-muted)]" title="No clean-vs-clean null: needs >= 2 clean repetitions">
                              no null
                            </span>
                          ) : (
                            <span className="text-[var(--text-secondary)]">
                              {drift.attack?.toFixed(2)} vs {drift.null?.toFixed(2)}
                            </span>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <div className="px-4 py-2 border-t border-[var(--border-subtle)] text-[10px] text-[var(--text-muted)]">
              CPR is <span className="font-mono">n/a</span> when no run compromised the entry agent —
              an empty denominator means the question was never asked, not that propagation never
              happened. Trajectory drift is only interpretable against its clean-vs-clean null.
            </div>
          </div>
        </section>
      )}

      {/* Runs */}
      <section className="rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)] overflow-hidden">
        <div className="px-4 py-2.5 border-b border-[var(--border-subtle)] text-xs font-semibold text-[var(--text-primary)]">
          Runs ({runs.length})
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-[var(--surface-base)] text-[10px] uppercase tracking-wider text-[var(--text-muted)]">
              <tr>
                <th className="px-4 py-2 text-left font-semibold">Case</th>
                <th className="px-2 py-2 text-left font-semibold">Mode</th>
                <th className="px-2 py-2 text-left font-semibold">Rep</th>
                <th className="px-2 py-2 text-left font-semibold">Status</th>
                <th className="px-2 py-2 text-left font-semibold">Objective</th>
                <th className="px-2 py-2 text-left font-semibold">Containment</th>
                <th className="px-2 py-2 text-right font-semibold"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-subtle)]">
              {runs.map((run: RunSummary) => (
                <tr key={run.run_id} className="hover:bg-[var(--surface-base)]">
                  <td className="px-4 py-2 font-mono font-semibold text-[var(--text-primary)]">{run.case_id}</td>
                  <td className="px-2 py-2 font-mono text-[10px] text-[var(--text-secondary)]">{run.mode}</td>
                  <td className="px-2 py-2 font-mono text-[10px] text-[var(--text-secondary)]">{run.repetition_index}</td>
                  <td className="px-2 py-2 font-mono text-[10px] text-[var(--text-secondary)]">{run.status}</td>
                  <td className="px-2 py-2">
                    {run.verdict ? (
                      <span className={`rounded border px-1.5 py-0.5 font-mono text-[10px] ${OBJECTIVE_STYLES[run.verdict.objective.level]}`}>
                        {run.verdict.objective.level}
                      </span>
                    ) : (
                      <span className="font-mono text-[10px] text-[var(--text-muted)]">baseline</span>
                    )}
                  </td>
                  <td className="px-2 py-2 font-mono text-[10px] text-[var(--text-secondary)]">
                    {run.verdict?.containment.label ?? '—'}
                  </td>
                  <td className="px-2 py-2 text-right">
                    <Link href={`/lab/runs/${run.run_id}`} className="text-[var(--primary)] hover:underline">
                      trace →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

function MetricCard({
  label, value, sub, muted,
}: {
  label: string
  value: string
  sub?: string
  muted?: boolean
}) {
  return (
    <div className="rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)] p-3">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">{label}</div>
      <div className={`mt-1 font-mono text-xl font-bold ${muted ? 'text-[var(--text-muted)]' : 'text-[var(--text-primary)]'}`}>
        {value}
      </div>
      {sub && <div className="mt-0.5 font-mono text-[10px] text-[var(--text-muted)]">{sub}</div>}
    </div>
  )
}
