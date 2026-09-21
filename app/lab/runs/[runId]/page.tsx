"use client"
import React, { use, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import {
  ArrowLeft, Download, GitBranch, ShieldAlert, Activity, AlertTriangle, Crosshair,
} from 'lucide-react'
import {
  labService, CATEGORY_STYLES, CeeSnapshot, IMPACT_STYLES, OBJECTIVE_STYLES,
  RunDetail, TraceEvent, Verdict,
} from '@/lib/lab-service'

/** Plain-language gloss for each event type, so the timeline is readable by
 *  someone who has not memorised §8's vocabulary. */
const EVENT_LABELS: Record<string, string> = {
  run_started: 'run started',
  cee_loaded: 'environment loaded',
  config_snapshot: 'config recorded',
  run_finished: 'run finished',
  artifact_planted: 'attacker artifact planted',
  artifact_observed: 'artifact entered context',
  agent_step_started: 'step started',
  agent_output: 'proposed an action',
  action_parse_failed: 'unparseable action',
  agent_finished: 'finished',
  message_sent: 'sent message',
  message_delivered: 'message delivered',
  message_denied: 'message DENIED',
  message_received: 'received message',
  tool_requested: 'requested tool',
  tool_executed: 'tool executed',
  tool_denied: 'tool DENIED',
  tool_error: 'tool error',
  state_read: 'read shared state',
  state_write: 'wrote shared state',
}

function summarize(value: unknown, max = 160): string {
  if (value === null || value === undefined) return ''
  const text = typeof value === 'string' ? value : JSON.stringify(value)
  return text.length > max ? `${text.slice(0, max)}…` : text
}

export default function LabRunPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = use(params)

  const [run, setRun] = useState<RunDetail | null>(null)
  const [baseline, setBaseline] = useState<RunDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<number | null>(null)
  const [highlighted, setHighlighted] = useState<number[]>([])
  const [showDiff, setShowDiff] = useState(false)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const detail = await labService.fetchRun(runId)
        if (cancelled) return
        setRun(detail)

        if (detail.baseline_run_id) {
          // Every §9 definition is baseline-relative, so the paired clean run
          // is part of reading this one, not an optional extra.
          try {
            const pair = await labService.fetchRun(detail.baseline_run_id)
            if (!cancelled) setBaseline(pair)
          } catch {
            if (!cancelled) setBaseline(null)
          }
        }
      } catch (err) {
        if (!cancelled) setError(String(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [runId])

  const byStep = useMemo(() => {
    const map = new Map<number, TraceEvent>()
    run?.events.forEach((e) => map.set(e.step, e))
    return map
  }, [run])

  /** Full transitive closure of derived_from — the same walk the evaluator
   *  uses to decide whether an event is attack-derived. */
  const closure = useMemo(() => {
    if (selected === null) return []
    const seen: number[] = []
    const frontier = [selected]
    while (frontier.length) {
      const step = frontier.shift()!
      if (seen.includes(step)) continue
      seen.push(step)
      byStep.get(step)?.derived_from.forEach((p) => {
        if (!seen.includes(p)) frontier.push(p)
      })
    }
    return seen
  }, [selected, byStep])

  const agents = useMemo(() => {
    const set = new Set<string>()
    run?.events.forEach((e) => e.agent_id && set.add(e.agent_id))
    return Array.from(set).sort()
  }, [run])

  const cleanSignatures = useMemo(() => {
    const set = new Set<string>()
    baseline?.events.forEach((e) => set.add(`${e.event_type}|${e.agent_id}|${e.tool}`))
    return set
  }, [baseline])

  const downloadEvidence = async () => {
    try {
      const bundle = await labService.fetchEvidence(runId)
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `redguard-evidence-${runId}.json`)
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(String(err))
    }
  }

  if (loading) return <div className="p-8 text-center text-xs text-[var(--text-muted)]">Loading trace…</div>

  if (error || !run) {
    return (
      <div className="space-y-4">
        <Link href="/lab" className="inline-flex items-center gap-1 text-xs text-[var(--primary)] font-semibold hover:underline">
          <ArrowLeft className="h-3 w-3" /> Back to Lab
        </Link>
        <div className="flex items-start gap-2 p-3 rounded-[var(--radius)] border border-[var(--danger)]/30 bg-[var(--danger-bg)] text-xs text-[var(--danger)]">
          <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
          <span className="font-mono break-all">{error ?? 'Run not found'}</span>
        </div>
      </div>
    )
  }

  const verdict = run.verdict

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 border-b border-[var(--border-subtle)] pb-4">
        <div>
          <Link href={`/lab/experiments/${run.experiment_id}`} className="inline-flex items-center gap-1 text-xs text-[var(--primary)] font-semibold hover:underline mb-2">
            <ArrowLeft className="h-3 w-3" /> Back to experiment
          </Link>
          <div className="flex items-center gap-2 text-xs font-semibold text-[var(--primary)] uppercase tracking-wider mb-1">
            <Activity className="h-4 w-4" /> Trace · {run.mode}
          </div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-tight font-mono">{run.case_id}</h1>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            {run.event_count} events · repetition {run.repetition_index} · status {run.status}
            {run.invalid_reason && (
              <span className="text-[var(--danger)]"> · {run.invalid_reason}</span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {baseline && (
            <button
              onClick={() => setShowDiff((v) => !v)}
              className={`inline-flex items-center gap-1.5 rounded-[var(--radius)] border px-3 py-1.5 text-xs font-semibold ${
                showDiff
                  ? 'border-[var(--primary)]/40 bg-[var(--primary)]/10 text-[var(--primary)]'
                  : 'border-[var(--border-default)] bg-[var(--surface-base)] text-[var(--text-primary)] hover:bg-[var(--surface-overlay)]'
              }`}
            >
              <GitBranch className="h-3.5 w-3.5" /> vs clean
            </button>
          )}
          {run.mode === 'ATTACK' && (
            <button
              onClick={downloadEvidence}
              className="inline-flex items-center gap-1.5 rounded-[var(--radius)] border border-[var(--border-default)] bg-[var(--surface-base)] px-3 py-1.5 text-xs font-semibold text-[var(--text-primary)] hover:bg-[var(--surface-overlay)]"
            >
              <Download className="h-3.5 w-3.5" /> Evidence bundle
            </button>
          )}
        </div>
      </div>

      {/* Verdict — four dimensions, never collapsed (§9) */}
      {verdict && <VerdictPanel verdict={verdict} onHighlight={setHighlighted} highlighted={highlighted} />}

      {/* Timeline */}
      <section className="rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)] overflow-hidden">
        <div className="px-4 py-2.5 border-b border-[var(--border-subtle)] flex flex-wrap items-center justify-between gap-2">
          <span className="text-xs font-semibold text-[var(--text-primary)]">
            Event timeline{agents.length > 0 && <span className="text-[var(--text-muted)] font-normal"> · lanes: {agents.join(' · ')}</span>}
          </span>
          <div className="flex items-center gap-3 text-[10px] text-[var(--text-muted)]">
            {selected !== null && (
              <span className="font-mono text-[var(--primary)]">
                provenance of #{selected}: {closure.length} events
              </span>
            )}
            {(selected !== null || highlighted.length > 0) && (
              <button
                onClick={() => { setSelected(null); setHighlighted([]) }}
                className="text-[var(--primary)] hover:underline"
              >
                clear
              </button>
            )}
          </div>
        </div>

        <div className="max-h-[38rem] overflow-y-auto divide-y divide-[var(--border-subtle)]">
          {run.events.map((event) => {
            const inClosure = closure.includes(event.step)
            const isEvidence = highlighted.includes(event.step)
            const signature = `${event.event_type}|${event.agent_id}|${event.tool}`
            const absentInClean = showDiff && !!event.agent_id && !cleanSignatures.has(signature)

            return (
              <button
                key={event.step}
                onClick={() => setSelected(selected === event.step ? null : event.step)}
                className={`w-full text-left px-4 py-2 flex items-start gap-3 transition-colors ${
                  isEvidence
                    ? 'bg-[var(--warning-bg)]'
                    : inClosure
                      ? 'bg-[var(--primary)]/10'
                      : 'hover:bg-[var(--surface-base)]'
                }`}
              >
                <span className="font-mono text-[10px] text-[var(--text-muted)] w-8 shrink-0 pt-0.5">
                  #{event.step}
                </span>

                {/* Agent lane */}
                <span className="w-16 shrink-0">
                  {event.agent_id ? (
                    <span className="inline-block rounded border border-[var(--border-default)] bg-[var(--surface-base)] px-1.5 py-0.5 font-mono text-[10px] font-bold text-[var(--text-primary)]">
                      {event.agent_id}
                    </span>
                  ) : (
                    <span className="font-mono text-[10px] text-[var(--text-muted)]">sys</span>
                  )}
                </span>

                <span className="flex-1 min-w-0">
                  <span className="flex flex-wrap items-center gap-1.5">
                    <span className={`rounded border px-1.5 py-0.5 font-mono text-[10px] ${CATEGORY_STYLES[event.category] ?? ''}`}>
                      {EVENT_LABELS[event.event_type] ?? event.event_type}
                    </span>
                    {event.tool && (
                      <span className="font-mono text-[10px] font-semibold text-[var(--text-primary)]">{event.tool}</span>
                    )}
                    {event.authorized === false && (
                      <span className="rounded border border-[var(--danger)]/40 bg-[var(--danger-bg)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--danger)]">
                        denied
                      </span>
                    )}
                    {event.content_tag && (
                      /* An observational label, not a trust level (§8). */
                      <span className="font-mono text-[10px] text-[var(--text-muted)]">
                        tag:{event.content_tag}
                      </span>
                    )}
                    {absentInClean && (
                      <span className="rounded border border-[var(--warning)]/40 bg-[var(--warning-bg)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--warning)]">
                        absent in clean
                      </span>
                    )}
                    {event.derived_from.length > 0 && (
                      <span className="font-mono text-[10px] text-[var(--text-muted)]">
                        ← {event.derived_from.map((d) => `#${d}`).join(' ')}
                      </span>
                    )}
                  </span>

                  {(event.arguments != null || event.result != null) && (
                    <span className="mt-0.5 block font-mono text-[10px] text-[var(--text-secondary)] break-all">
                      {summarize(event.arguments ?? event.result)}
                    </span>
                  )}
                </span>
              </button>
            )
          })}
        </div>

        <div className="px-4 py-2 border-t border-[var(--border-subtle)] text-[10px] text-[var(--text-muted)]">
          Click any event to trace its recorded derivation back to the artifact. Those edges are
          <em> observed derivation</em> — content present in an agent&apos;s context when it acted —
          not a claim about why the model did what it did.
        </div>
      </section>

      {/* CEE diff */}
      {run.cee_before && run.cee_after && (
        <CeeDiff before={run.cee_before} after={run.cee_after} />
      )}
    </div>
  )
}

function VerdictPanel({
  verdict, onHighlight, highlighted,
}: {
  verdict: Verdict
  onHighlight: (steps: number[]) => void
  highlighted: number[]
}) {
  const isActive = (evidence: number[]) =>
    evidence.length > 0 && evidence.every((e) => highlighted.includes(e)) && highlighted.length === evidence.length

  const toggle = (evidence: number[]) => onHighlight(isActive(evidence) ? [] : evidence)

  return (
    <section className="grid gap-3 md:grid-cols-4">
      {/* Agent impact */}
      <div className="rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)] p-3">
        <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
          <ShieldAlert className="h-3 w-3" /> Agent impact
        </div>
        <div className="space-y-1.5">
          {Object.entries(verdict.agent_impact).map(([agent, impact]) => (
            <button
              key={agent}
              onClick={() => toggle(impact.evidence)}
              disabled={impact.evidence.length === 0}
              className="flex w-full items-center justify-between gap-2 text-left disabled:cursor-default"
            >
              <span className="font-mono text-xs font-bold text-[var(--text-primary)]">{agent}</span>
              <span className={`rounded border px-1.5 py-0.5 font-mono text-[10px] ${IMPACT_STYLES[impact.level]}`}>
                {impact.level}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Objective */}
      <button
        onClick={() => toggle(verdict.objective.evidence)}
        disabled={verdict.objective.evidence.length === 0}
        className="rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)] p-3 text-left disabled:cursor-default"
      >
        <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
          <Crosshair className="h-3 w-3" /> Attacker objective
        </div>
        <span className={`inline-block rounded border px-1.5 py-0.5 font-mono text-[10px] ${OBJECTIVE_STYLES[verdict.objective.level]}`}>
          {verdict.objective.level}
        </span>
        {verdict.objective.evidence.length > 0 && (
          <div className="mt-2 font-mono text-[10px] text-[var(--text-muted)]">
            evidence: {verdict.objective.evidence.map((e) => `#${e}`).join(' ')}
          </div>
        )}
      </button>

      {/* Containment */}
      <button
        onClick={() => toggle(verdict.containment.evidence)}
        disabled={verdict.containment.evidence.length === 0}
        className="rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)] p-3 text-left disabled:cursor-default"
      >
        <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
          Containment
        </div>
        <div className="font-mono text-xs font-bold text-[var(--text-primary)]">{verdict.containment.label}</div>
        {verdict.containment.mechanism && (
          <div className="mt-1 font-mono text-[10px] text-[var(--text-secondary)]">
            {verdict.containment.mechanism}
          </div>
        )}
      </button>

      {/* System outcome */}
      <div className="rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)] p-3">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
          System outcome
        </div>
        <div className="font-mono text-xs font-bold text-[var(--text-primary)]">{verdict.system_outcome}</div>
        <div className="mt-2 text-[10px] text-[var(--text-muted)] leading-snug">
          Four independent dimensions. They are deliberately never collapsed into one
          safe/unsafe score.
        </div>
      </div>
    </section>
  )
}

function CeeDiff({ before, after }: { before: CeeSnapshot; after: CeeSnapshot }) {
  const channels = ['files', 'web', 'db', 'kv']
  const changes = channels.flatMap((channel) => {
    const oldMap: Record<string, unknown> = before[channel] ?? {}
    const newMap: Record<string, unknown> = after[channel] ?? {}
    return Object.keys({ ...oldMap, ...newMap })
      .filter((key) => JSON.stringify(oldMap[key]) !== JSON.stringify(newMap[key]))
      .map((key) => ({ channel, key, before: oldMap[key], after: newMap[key] }))
  })

  if (changes.length === 0) return null

  return (
    <section className="rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)] overflow-hidden">
      <div className="px-4 py-2.5 border-b border-[var(--border-subtle)] text-xs font-semibold text-[var(--text-primary)]">
        Environment changes ({changes.length})
      </div>
      <div className="divide-y divide-[var(--border-subtle)]">
        {changes.map((change) => (
          <div key={`${change.channel}:${change.key}`} className="px-4 py-2 text-xs">
            <div className="font-mono text-[10px] text-[var(--text-muted)]">
              {change.channel} · {change.key}
            </div>
            <div className="mt-1 font-mono text-[10px] text-[var(--text-secondary)] break-all">
              {summarize(change.after, 220)}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
