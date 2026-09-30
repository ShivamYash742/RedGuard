"use client"
import React, { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { AlertTriangle, ArrowLeft, Loader2 } from 'lucide-react'
import {
  labService, ArmComparison, CompareResult, Experiment, PairedDifference, RateComparison, armName, formatRate,
} from '@/lib/lab-service'
import EmptyState from '@/components/EmptyState'
import { TableSkeleton } from '@/components/Skeletons'

const METRICS: { key: 'asr' | 'icr' | 'partial_rate'; label: string }[] = [
  { key: 'asr', label: 'Objective reached' },
  { key: 'icr', label: 'Entry agent compromised' },
  { key: 'partial_rate', label: 'Objective partially reached' },
]

const pct = (x: number, signed = false) => `${signed && x > 0 ? '+' : ''}${(x * 100).toFixed(0)}%`

export default function LabComparePage() {
  const [experiments, setExperiments] = useState<Experiment[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [result, setResult] = useState<CompareResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [comparing, setComparing] = useState(false)

  const compare = useCallback((ids: string[]) => {
    setComparing(true)
    setError(null)
    // In the URL, so a comparison can be reopened and shared.
    window.history.replaceState(null, '', `/lab/compare?experiments=${ids.join(',')}`)
    labService.fetchCompare(ids)
      .then(setResult)
      .catch((err) => {
        setResult(null)
        setError(String(err))
      })
      .finally(() => setComparing(false))
  }, [])

  useEffect(() => {
    labService.fetchExperiments()
      .then((list) => {
        setExperiments(list)
        const fromUrl = new URLSearchParams(window.location.search).get('experiments')?.split(',').filter(Boolean) ?? []
        setSelected(fromUrl)
        if (fromUrl.length >= 2) compare(fromUrl)
      })
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false))
  }, [compare])

  const toggle = (id: string) => setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))

  if (loading) return <TableSkeleton />

  return (
    <div className="space-y-6">
      <header className="border-b border-[var(--border-subtle)] pb-5">
        <Link href="/lab" className="inline-flex items-center gap-1 text-sm font-semibold text-[var(--primary)] hover:underline">
          <ArrowLeft className="h-3.5 w-3.5" /> Lab
        </Link>
        <h1 className="mt-2 text-2xl font-bold tracking-tight text-[var(--text-primary)]">Compare defences</h1>
        <p className="mt-1 max-w-3xl text-sm text-[var(--text-secondary)]">
          Pick experiments that differ only in their defence: same model, step budget and replay mode. Each comparison
          lines the two arms up case by case, because the case, not the run, is what these results generalise over.
        </p>
      </header>

      <section aria-label="Experiments to compare" className="overflow-hidden rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)]">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border-subtle)] px-4 py-3">
          <h2 className="text-base font-semibold text-[var(--text-primary)]">
            Experiments <span className="font-normal text-[var(--text-secondary)]">· {selected.length} selected</span>
          </h2>
          <button onClick={() => compare(selected)} disabled={selected.length < 2 || comparing}
            className="inline-flex items-center gap-1.5 rounded-[var(--radius)] bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-[var(--primary-foreground)] hover:bg-[var(--primary-hover)] disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]">
            {comparing && <Loader2 className="h-4 w-4 animate-spin" />} Compare
          </button>
        </div>
        {experiments.length === 0 ? (
          <EmptyState title="No experiments yet" description="Run at least two arms from the Lab, then compare them here." />
        ) : (
          <ul className="max-h-80 divide-y divide-[var(--border-subtle)] overflow-y-auto">
            {experiments.map((e) => {
              const config = e.config as { scripted?: boolean; model?: { model?: string } }
              return (
                <li key={e.experiment_id}>
                  <label className="grid cursor-pointer grid-cols-[1.25rem_minmax(0,1fr)_auto] items-center gap-x-3 px-4 py-2.5 hover:bg-[var(--surface-base)] sm:grid-cols-[1.25rem_minmax(0,1fr)_11rem_minmax(0,12rem)_10rem]">
                    <input type="checkbox" checked={selected.includes(e.experiment_id)} onChange={() => toggle(e.experiment_id)} className="accent-[var(--primary)]" />
                    <span className="min-w-0 truncate text-sm text-[var(--text-primary)]">{e.name}</span>
                    <span className="text-sm font-semibold text-[var(--text-primary)]">{armName(e.arm)}</span>
                    <span className="hidden truncate font-mono text-xs text-[var(--text-secondary)] sm:block">{config.scripted ? 'scripted' : config.model?.model ?? 'model'}</span>
                    <span className="hidden text-xs tabular-nums text-[var(--text-secondary)] sm:block">{new Date(e.created_at).toLocaleString()}</span>
                  </label>
                </li>
              )
            })}
          </ul>
        )}
      </section>

      {error && (
        <div role="alert" className="flex items-start gap-2 rounded-[var(--radius)] border border-[var(--danger)]/30 bg-[var(--danger-bg)] p-3 text-sm text-[var(--text-primary)]">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--danger)]" />
          <span className="break-words">{error}</span>
        </div>
      )}

      {result && <Results result={result} />}
    </div>
  )
}

function Results({ result }: { result: CompareResult }) {
  const comparisons = Object.entries(result.comparisons)
  return (
    <>
      {result.warnings.length > 0 && (
        <div className="rounded-[var(--radius)] border border-[var(--warning)]/30 bg-[var(--warning-bg)] p-3 text-sm text-[var(--text-primary)]">
          {result.warnings.map((w) => <p key={w}>{w}</p>)}
        </div>
      )}

      <section aria-label="Arms" className="overflow-hidden rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)]">
        <h2 className="border-b border-[var(--border-subtle)] px-4 py-3 text-base font-semibold text-[var(--text-primary)]">Arms</h2>
        <div className="overflow-x-auto">
          <table className="research-table">
            <thead>
              <tr>
                <th>Defence</th>
                <th className="text-right">Valid runs</th>
                <th className="text-right">Objective reached</th>
                <th className="text-right">Entry compromised</th>
                <th className="text-right">Contained</th>
                <th className="text-right">Propagated</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(result.arms).map(([arm, s]) => (
                <tr key={arm}>
                  <td className="font-semibold">{armName(arm)}</td>
                  <td className="text-right font-mono tabular-nums">{s.n_valid}{s.n_invalid > 0 && <span className="text-[var(--text-secondary)]"> (+{s.n_invalid} invalid)</span>}</td>
                  <td className="text-right font-mono tabular-nums">{rateWithInterval(s.asr)}</td>
                  <td className="text-right font-mono tabular-nums">{rateWithInterval(s.icr)}</td>
                  <td className="text-right font-mono tabular-nums">{formatRate(s.containment_rate)}</td>
                  <td className="text-right font-mono tabular-nums">{formatRate(s.cpr)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {comparisons.length === 0 ? (
        <p className="text-sm text-[var(--text-secondary)]">
          None of the standard comparisons has both of its arms among these experiments.
        </p>
      ) : comparisons.map(([label, c]) => <Comparison key={label} label={label} c={c} />)}
    </>
  )
}

function rateWithInterval(rate: { value: number | null; ci: [number, number] | null }) {
  if (rate.value === null) return '—'
  return (
    <>
      {formatRate(rate.value)}
      {rate.ci && <span className="ml-1.5 text-xs text-[var(--text-secondary)]">{pct(rate.ci[0])}–{pct(rate.ci[1])}</span>}
    </>
  )
}

function Comparison({ label, c }: { label: string; c: ArmComparison }) {
  return (
    <section aria-label={label} className="overflow-hidden rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)]">
      <div className="border-b border-[var(--border-subtle)] px-4 py-3">
        <h2 className="text-base font-semibold text-[var(--text-primary)]">
          <span className="font-mono">{label}</span> · {armName(c.baseline_arm)} → {armName(c.variant_arm)}
        </h2>
        <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
          Differences are {armName(c.variant_arm)} minus {armName(c.baseline_arm)}: below zero, the defence lowered the rate.
        </p>
      </div>
      <div className="divide-y divide-[var(--border-subtle)]">
        {METRICS.map(({ key, label: name }) => <MetricRow key={key} name={name} m={c.metrics[key]} />)}
        <div className="grid gap-1 px-4 py-2.5 text-sm sm:grid-cols-[14rem_1fr]">
          <span className="text-[var(--text-primary)]">Contained</span>
          <span className="font-mono tabular-nums text-[var(--text-secondary)]">
            {formatRate(c.metrics.containment_rate.baseline)} → {formatRate(c.metrics.containment_rate.variant)}
            <span className="ml-3 font-sans">propagated {formatRate(c.metrics.cpr.baseline)} → {formatRate(c.metrics.cpr.variant)}
              {!c.metrics.cpr.comparable && ' (not comparable: n/a on one side)'}</span>
          </span>
        </div>
      </div>
      <p className="border-t border-[var(--border-subtle)] px-4 py-2 text-xs text-[var(--text-secondary)]">{c.caveat}</p>
    </section>
  )
}

function MetricRow({ name, m }: { name: string; m: RateComparison }) {
  return (
    <div className="grid items-center gap-x-4 gap-y-1.5 px-4 py-3 sm:grid-cols-[14rem_9rem_minmax(10rem,1fr)_minmax(12rem,16rem)]">
      <span className="text-sm text-[var(--text-primary)]">{name}</span>
      <span className="font-mono text-sm tabular-nums text-[var(--text-primary)]">
        {formatRate(m.baseline.value, 0)} → {formatRate(m.variant.value, 0)}
      </span>
      <DiffBar paired={m.paired} />
      <span className="text-xs text-[var(--text-secondary)]">{pairedReading(m.paired)}</span>
    </div>
  )
}

function pairedReading(p: PairedDifference): string {
  if (p.n_cases === 0) return 'No case ran under both arms.'
  const counts = `lower in ${p.cases_lower}, same in ${p.cases_equal}, higher in ${p.cases_higher} of ${p.n_cases} cases`
  if (p.excludes_zero === null) return `${counts}. Too few shared cases for an interval (needs 5).`
  return p.excludes_zero ? `${counts}. Consistent across cases.` : `${counts}. Not distinguishable from zero at this sample.`
}

/** Mean paired difference and its interval on a −100%…+100% axis. */
function DiffBar({ paired }: { paired: PairedDifference }) {
  const { mean_difference: mean, ci } = paired
  if (mean === null) return <span className="text-sm text-[var(--text-secondary)]">—</span>
  const x = (v: number) => `${((v + 1) / 2) * 100}%`
  return (
    <div className="flex items-center gap-3">
      <div className="relative h-4 min-w-[8rem] flex-1" role="img"
        aria-label={`mean difference ${pct(mean, true)}${ci ? `, 95% interval ${pct(ci[0], true)} to ${pct(ci[1], true)}` : ''}`}>
        <div className="absolute inset-x-0 top-1/2 h-px bg-[var(--border-default)]" />
        <div className="absolute top-0 h-4 w-px bg-[var(--text-secondary)]" style={{ left: '50%' }} />
        {ci && (
          <div className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-[var(--accent)]"
            style={{ left: x(ci[0]), width: `${Math.max(0.6, ((ci[1] - ci[0]) / 2) * 100)}%` }} />
        )}
        <div className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-[var(--surface-raised)] bg-[var(--text-primary)]"
          style={{ left: x(mean) }} />
      </div>
      <span className="whitespace-nowrap font-mono text-xs tabular-nums text-[var(--text-primary)]">{pct(mean, true)}</span>
    </div>
  )
}
