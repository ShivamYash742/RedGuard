"use client"
import React, { use, useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import {
  AlertTriangle, ArrowLeft, Download, GitBranch, Pause, Play, SkipBack, SkipForward, StepBack, StepForward,
} from 'lucide-react'
import {
  labService, CATEGORY_STYLES, CeeSnapshot, EVENT_LABELS, LiveEvent, RESOURCE_ARG_KEYS, RunDetail, Topology,
  TraceEvent, Verdict, containmentLabel, deriveRoute, describeEvent, toLiveEvent,
  IMPACT_LABELS, MECHANISM_LABELS, OBJECTIVE_LABELS, OUTCOME_LABELS, REFUSAL_REASONS,
} from '@/lib/lab_mode/lab-service'
import { ImpactGlyph, ObjectiveGlyph, PropagationStage, RouteLegend, SealGlyph } from '@/components/lab_mode/LabRoute'
import { AgentSwimlane } from '@/components/lab_mode/AgentSwimlane'
import { TableSkeleton } from '@/components/shared/Skeletons'

interface CaseInfo {
  title: string
  path: string[]
  entry: string
  channel: string
  location: string | null
  eligible: string[]
}

function caseInfo(raw: Record<string, unknown>): CaseInfo {
  const attack = (raw.attack ?? {}) as { injection_point?: string; delivery?: { channel?: string; location?: string } }
  const eligibility = (raw.eligibility ?? {}) as { expected_path?: string[]; eligible_downstream_agents?: string[] }
  return {
    title: String(raw.title ?? ''),
    path: eligibility.expected_path ?? ['A', 'B', 'C'],
    entry: attack.injection_point ?? 'A',
    channel: attack.delivery?.channel ?? 'files',
    location: attack.delivery?.location || null,
    eligible: eligibility.eligible_downstream_agents ?? [],
  }
}

/** Same key as `evaluator._event_signature`, so "absent in clean" here marks
 *  exactly what the evaluator counted as deviation. */
function eventSignature(event: TraceEvent): string {
  const args = (event.arguments ?? {}) as Record<string, unknown>
  const resource = RESOURCE_ARG_KEYS.filter((k) => k in args).map((k) => `${k}=${JSON.stringify(args[k])}`).join(',')
  return `${event.category}|${event.event_type}|${event.agent_id}|${event.tool}|${resource}`
}

function summarize(value: unknown, max = 160): string {
  if (value === null || value === undefined) return ''
  const text = typeof value === 'string' ? value : JSON.stringify(value)
  return text.length > max ? `${text.slice(0, max)}…` : text
}

const SPEEDS = [1, 2, 4] as const

export default function LabRunPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = use(params)

  const [run, setRun] = useState<RunDetail | null>(null)
  const [baseline, setBaseline] = useState<RunDetail | null>(null)
  const [info, setInfo] = useState<CaseInfo | null>(null)
  const [topology, setTopology] = useState<Topology | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const [cursor, setCursor] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>(1)
  const [touched, setTouched] = useState(false)
  const [selected, setSelected] = useState<number | null>(null)
  const [highlighted, setHighlighted] = useState<number[]>([])
  const [showDiff, setShowDiff] = useState(false)
  const listRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const detail = await labService.fetchRun(runId)
        if (cancelled) return
        setRun(detail)
        setCursor(Math.max(0, detail.events.length - 1))
        const [pair, raw, topologies] = await Promise.all([
          // Every §9 definition is baseline-relative, so the paired clean run
          // is part of reading this one, not an optional extra.
          detail.baseline_run_id ? labService.fetchRun(detail.baseline_run_id).catch(() => null) : Promise.resolve(null),
          labService.fetchCase(detail.case_id).catch(() => null),
          labService.fetchTopologies().catch(() => null),
        ])
        if (cancelled) return
        setBaseline(pair)
        if (raw) setInfo(caseInfo(raw))
        setTopology(topologies?.topologies[0] ?? null)
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

  const live = useMemo<LiveEvent[]>(() => run?.events.map(toLiveEvent) ?? [], [run])
  const last = live.length - 1
  const atEnd = cursor >= last

  useEffect(() => {
    if (!playing) return
    const timer = setInterval(() => {
      setCursor((c) => {
        if (c >= last) {
          setPlaying(false)
          return c
        }
        return c + 1
      })
    }, 480 / speed)
    return () => clearInterval(timer)
  }, [playing, speed, last])

  // Keep the cursor row in view by scrolling the list itself — never the page.
  useEffect(() => {
    const list = listRef.current
    const row = list?.querySelector<HTMLElement>(`[data-index="${cursor}"]`)
    if (!list || !row) return
    const top = row.offsetTop // the list is `relative`, so this is already list-relative
    if (top < list.scrollTop || top + row.offsetHeight > list.scrollTop + list.clientHeight) {
      list.scrollTop = top - list.clientHeight / 2 + row.offsetHeight / 2
    }
  }, [cursor])

  const byStep = useMemo(() => {
    const map = new Map<number, TraceEvent>()
    run?.events.forEach((e) => map.set(e.step, e))
    return map
  }, [run])

  /** Full transitive closure of derived_from — the walk the evaluator uses
   *  to decide whether an event is attack-derived. */
  const closure = useMemo(() => {
    if (selected === null) return new Set<number>()
    const seen = new Set<number>()
    const frontier = [selected]
    while (frontier.length) {
      const step = frontier.pop()!
      if (seen.has(step)) continue
      seen.add(step)
      byStep.get(step)?.derived_from.forEach((p) => frontier.push(p))
    }
    return seen
  }, [selected, byStep])

  const cleanSignatures = useMemo(() => new Set(baseline?.events.map(eventSignature) ?? []), [baseline])

  const go = (index: number) => {
    setTouched(true)
    setCursor(Math.max(0, Math.min(last, index)))
  }

  const togglePlay = () => {
    setTouched(true)
    if (playing) return setPlaying(false)
    if (atEnd) setCursor(0)
    setPlaying(true)
  }

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

  if (loading) return <TableSkeleton />

  if (!run) {
    return (
      <div className="space-y-4">
        <Link href="/lab" className="inline-flex items-center gap-1 text-sm font-semibold text-[var(--primary)] hover:underline">
          <ArrowLeft className="h-3.5 w-3.5" /> Lab
        </Link>
        <ErrorLine message={error ?? 'Run not found'} />
      </div>
    )
  }

  const verdict = run.verdict
  const attack = run.mode === 'ATTACK'
  const path = info?.path ?? ['A', 'B', 'C']
  const route = deriveRoute(live, path, live[cursor]?.step ?? -1)
  const current = live[cursor]

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 border-b border-[var(--border-subtle)] pb-5 md:flex-row md:items-end md:justify-between">
        <div className="min-w-0">
          <Link href={`/lab/experiments/${run.experiment_id}`} className="inline-flex items-center gap-1 text-sm font-semibold text-[var(--primary)] hover:underline">
            <ArrowLeft className="h-3.5 w-3.5" /> Experiment
          </Link>
          <h1 className="mt-2 text-2xl font-bold tracking-tight text-[var(--text-primary)]">
            <span className="font-mono">{run.case_id}</span>
            {info?.title && <span className="font-normal text-[var(--text-secondary)]"> · {info.title}</span>}
          </h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            <span className="font-semibold text-[var(--text-primary)]">{attack ? 'Attack run' : 'Clean baseline'}</span>
            {' · '}repetition {run.repetition_index} · {run.event_count} events · {run.status.toLowerCase()}
            {run.invalid_reason && <span className="text-[var(--text-primary)]"> · {run.invalid_reason}</span>}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {baseline && (
            <button onClick={() => setShowDiff((v) => !v)} aria-pressed={showDiff}
              className={`inline-flex items-center gap-1.5 rounded-[var(--radius)] border px-3 py-2 text-sm font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--primary)] ${showDiff
                ? 'border-[var(--primary)] bg-[color-mix(in_srgb,var(--primary)_12%,transparent)] text-[var(--text-primary)]'
                : 'border-[var(--border-default)] bg-[var(--surface-raised)] text-[var(--text-primary)] hover:border-[var(--text-secondary)]'}`}>
              <GitBranch className="h-3.5 w-3.5" /> Mark what the clean run never did
            </button>
          )}
          {attack && (
            <button onClick={downloadEvidence}
              className="inline-flex items-center gap-1.5 rounded-[var(--radius)] border border-[var(--border-default)] bg-[var(--surface-raised)] px-3 py-2 text-sm font-semibold text-[var(--text-primary)] hover:border-[var(--text-secondary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--primary)]">
              <Download className="h-3.5 w-3.5" /> Evidence bundle
            </button>
          )}
        </div>
      </header>

      {error && <ErrorLine message={error} />}

      {verdict && <VerdictRow verdict={verdict} path={path} highlighted={highlighted} onHighlight={setHighlighted} />}

      <section aria-label="Replay" className="rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)]"
        onKeyDown={(e) => {
          const tag = (e.target as HTMLElement).tagName
          if (e.key === ' ' && tag !== 'BUTTON' && tag !== 'INPUT') {
            e.preventDefault()
            togglePlay()
          }
        }}>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border-subtle)] px-4 py-3">
          <h2 className="text-base font-semibold text-[var(--text-primary)]">Replay</h2>
          <RouteLegend />
        </div>
        <div className="overflow-x-auto px-4 pt-4">
          <PropagationStage
            path={path}
            entry={attack ? info?.entry ?? null : null}
            channel={attack ? info?.channel ?? null : null}
            location={info?.location}
            eligible={info?.eligible ?? []}
            route={route}
            verdict={verdict}
            showVerdict={atEnd}
            toolAuth={topology?.tool_auth}
            live={touched}
          />
        </div>

        <div className="space-y-3 border-t border-[var(--border-subtle)] px-4 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <TransportButton label="Start" onClick={() => go(0)}><SkipBack className="h-4 w-4" /></TransportButton>
            <TransportButton label="Step back" onClick={() => go(cursor - 1)}><StepBack className="h-4 w-4" /></TransportButton>
            <button onClick={togglePlay} aria-label={playing ? 'Pause' : atEnd ? 'Replay from the start' : 'Play'}
              className="inline-flex h-9 items-center gap-1.5 rounded-[var(--radius)] bg-[var(--primary)] px-3 text-sm font-semibold text-[var(--primary-foreground)] hover:bg-[var(--primary-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]">
              {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
              {playing ? 'Pause' : atEnd ? 'Replay' : 'Play'}
            </button>
            <TransportButton label="Step forward" onClick={() => go(cursor + 1)}><StepForward className="h-4 w-4" /></TransportButton>
            <TransportButton label="End" onClick={() => go(last)}><SkipForward className="h-4 w-4" /></TransportButton>
            <button onClick={() => setSpeed((s) => SPEEDS[(SPEEDS.indexOf(s) + 1) % SPEEDS.length])} aria-label={`Playback speed ${speed}×`}
              className="h-9 rounded-[var(--radius)] border border-[var(--border-default)] px-2.5 font-mono text-sm text-[var(--text-primary)] hover:border-[var(--text-secondary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--primary)]">
              {speed}×
            </button>
            <p className="ml-1 min-w-0 flex-1 truncate text-sm" aria-live="polite">
              <span className="font-mono tabular-nums text-[var(--text-secondary)]">step {current?.step ?? 0} · {cursor + 1}/{live.length}</span>
              {current && <span className="ml-2 font-mono text-[var(--text-primary)]">{describeEvent(current)}</span>}
            </p>
          </div>
          <Scrubber events={live} cursor={cursor} onSeek={go} />
          <p className="text-xs text-[var(--text-secondary)]">
            Space plays and pauses; arrow keys step once the scrubber has focus. The final shapes, seal and objective
            appear at the last event: before it, the stage shows only what had been observed so far.
          </p>
        </div>
      </section>

      <section aria-label="When each agent worked" className="rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)]">
        <h2 className="border-b border-[var(--border-subtle)] px-4 py-3 text-base font-semibold text-[var(--text-primary)]">When each agent worked</h2>
        <div className="px-4 py-4">
          <AgentSwimlane events={live} agents={path} cursorStep={current?.step} />
        </div>
      </section>

      <section aria-label="Event timeline" className="overflow-hidden rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)]">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border-subtle)] px-4 py-3">
          <h2 className="text-base font-semibold text-[var(--text-primary)]">Event timeline</h2>
          <div className="flex items-center gap-3 text-sm">
            {selected !== null && <span className="font-mono text-[var(--text-secondary)]">provenance of #{selected}: {closure.size} events</span>}
            {(selected !== null || highlighted.length > 0) && (
              <button onClick={() => { setSelected(null); setHighlighted([]) }} className="font-semibold text-[var(--primary)] hover:underline">
                Clear
              </button>
            )}
          </div>
        </div>

        <div ref={listRef} className="relative max-h-[34rem] overflow-y-auto">
          {run.events.map((event, index) => {
            const inClosure = closure.has(event.step)
            const isEvidence = highlighted.includes(event.step)
            const future = index > cursor
            const absentInClean = showDiff && !!event.agent_id && !cleanSignatures.has(eventSignature(event))
            const reason = event.authorized === false ? (event.metadata?.reason as string | undefined) : undefined
            const tint = index === cursor
              ? 'bg-[color-mix(in_srgb,var(--primary)_14%,transparent)]'
              : isEvidence ? 'bg-[var(--warning-bg)]'
                : inClosure ? 'bg-[color-mix(in_srgb,var(--accent)_14%,transparent)]'
                  : 'hover:bg-[var(--surface-base)]'
            return (
              <button key={event.step} data-index={index}
                onClick={() => { go(index); setSelected(selected === event.step ? null : event.step) }}
                className={`flex w-full items-start gap-3 border-b border-[var(--border-subtle)] px-4 py-2 text-left transition-[background-color,opacity] duration-150 last:border-b-0 focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--primary)] ${tint} ${future ? 'opacity-45' : ''}`}>
                <span className="w-9 shrink-0 pt-0.5 font-mono text-xs tabular-nums text-[var(--text-secondary)]">#{event.step}</span>
                <span className="w-10 shrink-0 pt-0.5 font-mono text-xs font-bold text-[var(--text-primary)]">{event.agent_id ?? <span className="font-normal text-[var(--text-secondary)]">sys</span>}</span>
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-1.5">
                    <span className={`rounded border px-1.5 py-0.5 text-xs ${CATEGORY_STYLES[event.category] ?? ''}`}>
                      {EVENT_LABELS[event.event_type] ?? event.event_type}
                    </span>
                    {event.tool && <span className="font-mono text-xs font-semibold text-[var(--text-primary)]">{event.tool}</span>}
                    {event.authorized === false && (
                      <span className="inline-flex items-center gap-1 text-xs text-[var(--text-primary)]">
                        <SealGlyph size={10} /> refused{reason ? ` · ${REFUSAL_REASONS[reason] ?? reason}` : ''}
                      </span>
                    )}
                    {absentInClean && (
                      <span className="rounded border border-[var(--warning)]/40 bg-[var(--warning-bg)] px-1.5 py-0.5 text-xs text-[var(--text-primary)]">
                        not in the clean run
                      </span>
                    )}
                    {event.content_tag && (
                      /* An observational label, not a trust level (§8). */
                      <span className="text-xs text-[var(--text-secondary)]">{event.content_tag.replace('_', ' ')}</span>
                    )}
                    {event.derived_from.length > 0 && (
                      <span className="font-mono text-xs text-[var(--text-secondary)]">← {event.derived_from.map((d) => `#${d}`).join(' ')}</span>
                    )}
                  </span>
                  {(event.arguments != null || event.result != null) && (
                    <span className="mt-0.5 block break-all font-mono text-xs text-[var(--text-secondary)]">{summarize(event.arguments ?? event.result)}</span>
                  )}
                </span>
              </button>
            )
          })}
        </div>

        <p className="border-t border-[var(--border-subtle)] px-4 py-2 text-xs text-[var(--text-secondary)]">
          Selecting an event moves the replay there and traces its recorded derivation back to the artifact. Those links
          are observed derivation, content present in an agent&apos;s context when it acted, not a claim about why the
          model did what it did. &ldquo;Not in the clean run&rdquo; compares against the paired clean run
          {verdict?.baseline_runs && verdict.baseline_runs > 1 ? `; the verdict itself was judged against ${verdict.baseline_runs} clean runs` : ''}.
        </p>
      </section>

      {run.cee_before && run.cee_after && <CeeDiff before={run.cee_before} after={run.cee_after} />}
    </div>
  )
}

function ErrorLine({ message }: { message: string }) {
  return (
    <div role="alert" className="flex items-start gap-2 rounded-[var(--radius)] border border-[var(--danger)]/30 bg-[var(--danger-bg)] p-3 text-sm text-[var(--text-primary)]">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--danger)]" />
      <span className="break-words">{message}</span>
    </div>
  )
}

function TransportButton({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick} aria-label={label} title={label}
      className="inline-flex h-9 w-9 items-center justify-center rounded-[var(--radius)] border border-[var(--border-default)] text-[var(--text-primary)] hover:border-[var(--text-secondary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--primary)]">
      {children}
    </button>
  )
}

/** One tick per event under a native range input: the input brings keyboard,
 *  pointer and screen-reader behaviour, the ticks show where the attack went.
 *  Red ticks are attack-derived, green ones refusals. */
function Scrubber({ events, cursor, onSeek }: { events: LiveEvent[]; cursor: number; onSeek: (i: number) => void }) {
  const derived = useMemo(() => {
    const tainted = new Set<number>()
    for (const e of events) {
      if (e.event_type === 'artifact_planted' || e.event_type === 'artifact_observed' || e.derived_from.some((p) => tainted.has(p))) tainted.add(e.step)
    }
    return tainted
  }, [events])
  const current = events[cursor]
  return (
    <div className="relative h-9">
      <div className="pointer-events-none absolute inset-x-0 top-1/2 flex -translate-y-1/2 items-center gap-px" aria-hidden>
        {events.map((e, i) => {
          const refused = e.authorized === false
          const hot = derived.has(e.step)
          return (
            <span key={e.step} className="flex-1 rounded-[1px] transition-opacity duration-150"
              style={{
                height: refused || hot ? 16 : 8,
                background: refused ? 'var(--success)' : hot ? 'var(--danger)' : 'var(--border-default)',
                opacity: i <= cursor ? 1 : 0.35,
              }} />
          )
        })}
      </div>
      <input type="range" min={0} max={Math.max(0, events.length - 1)} value={cursor}
        onChange={(e) => onSeek(Number(e.target.value))}
        aria-label="Replay position"
        aria-valuetext={current ? `step ${current.step}: ${describeEvent(current)}` : undefined}
        className="absolute inset-0 h-full w-full cursor-pointer appearance-none bg-transparent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)] [&::-moz-range-thumb]:h-7 [&::-moz-range-thumb]:w-1.5 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:bg-[var(--primary)] [&::-moz-range-track]:bg-transparent [&::-webkit-slider-runnable-track]:bg-transparent [&::-webkit-slider-thumb]:h-7 [&::-webkit-slider-thumb]:w-1.5 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-[var(--primary)]" />
    </div>
  )
}

/** The four dimensions in one row — never collapsed into a safe/unsafe score
 *  (§9). Each cell lights the trace events its claim rests on. */
function VerdictRow({ verdict, path, highlighted, onHighlight }: {
  verdict: Verdict; path: string[]; highlighted: number[]; onHighlight: (steps: number[]) => void
}) {
  const active = (evidence: number[]) =>
    evidence.length > 0 && evidence.length === highlighted.length && evidence.every((e) => highlighted.includes(e))
  const toggle = (evidence: number[]) => onHighlight(active(evidence) ? [] : evidence)
  const cell = 'min-w-0 px-4 py-3 text-left'
  const button = `${cell} transition-colors hover:bg-[var(--surface-base)] disabled:cursor-default disabled:hover:bg-transparent focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--primary)]`
  const head = 'text-xs font-semibold uppercase tracking-wide text-[var(--text-secondary)]'

  return (
    <section aria-label="Verdict" className="grid divide-y divide-[var(--border-subtle)] rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)] md:grid-cols-4 md:divide-x md:divide-y-0">
      <div className={cell}>
        <div className={head}>Agent impact</div>
        <div className="mt-2 space-y-1">
          {path.map((agent) => {
            const impact = verdict.agent_impact[agent]
            if (!impact) return null
            return (
              <button key={agent} onClick={() => toggle(impact.evidence)} disabled={impact.evidence.length === 0} aria-pressed={active(impact.evidence)}
                className="flex w-full items-center gap-2 rounded px-1 py-0.5 text-left text-sm hover:bg-[var(--surface-base)] disabled:cursor-default disabled:hover:bg-transparent">
                <ImpactGlyph level={impact.level} size={13} />
                <span className="font-mono font-bold text-[var(--text-primary)]">{agent}</span>
                <span className="text-[var(--text-primary)]">{IMPACT_LABELS[impact.level]}</span>
              </button>
            )
          })}
        </div>
      </div>
      <button className={button} onClick={() => toggle(verdict.objective.evidence)} disabled={verdict.objective.evidence.length === 0} aria-pressed={active(verdict.objective.evidence)}>
        <div className={head}>Attacker objective</div>
        <div className="mt-2 inline-flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
          <ObjectiveGlyph level={verdict.objective.level} size={14} /> {OBJECTIVE_LABELS[verdict.objective.level]}
        </div>
        {verdict.objective.evidence.length > 0 && (
          <div className="mt-1 font-mono text-xs text-[var(--text-secondary)]">evidence {verdict.objective.evidence.map((e) => `#${e}`).join(' ')}</div>
        )}
      </button>
      <button className={button} onClick={() => toggle(verdict.containment.evidence)} disabled={verdict.containment.evidence.length === 0} aria-pressed={active(verdict.containment.evidence)}>
        <div className={head}>Containment</div>
        <div className="mt-2 inline-flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
          {verdict.containment.status === 'CONTAINED' && <SealGlyph size={13} />} {containmentLabel(verdict)}
        </div>
        {verdict.containment.mechanism && (
          <div className="mt-1 text-xs text-[var(--text-secondary)]">{MECHANISM_LABELS[verdict.containment.mechanism] ?? verdict.containment.mechanism}</div>
        )}
      </button>
      <div className={cell}>
        <div className={head}>Benign task</div>
        <div className="mt-2 text-sm font-semibold text-[var(--text-primary)]">{OUTCOME_LABELS[verdict.system_outcome]}</div>
        <div className="mt-1 text-xs text-[var(--text-secondary)]">
          {verdict.baseline_runs && verdict.baseline_runs > 1
            ? `Judged against ${verdict.baseline_runs} clean runs of this case.`
            : 'Judged against its paired clean run.'}
        </div>
      </div>
    </section>
  )
}

function CeeDiff({ before, after }: { before: CeeSnapshot; after: CeeSnapshot }) {
  const changes = ['files', 'web', 'db', 'kv'].flatMap((channel) => {
    const oldMap: Record<string, unknown> = before[channel] ?? {}
    const newMap: Record<string, unknown> = after[channel] ?? {}
    return Object.keys({ ...oldMap, ...newMap })
      .filter((key) => JSON.stringify(oldMap[key]) !== JSON.stringify(newMap[key]))
      .map((key) => ({ channel, key, after: newMap[key] }))
  })
  if (changes.length === 0) return null
  return (
    <section aria-label="Environment changes" className="overflow-hidden rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)]">
      <h2 className="border-b border-[var(--border-subtle)] px-4 py-3 text-base font-semibold text-[var(--text-primary)]">
        What the run changed <span className="font-normal text-[var(--text-secondary)]">· {changes.length}</span>
      </h2>
      <div className="divide-y divide-[var(--border-subtle)]">
        {changes.map((change) => (
          <div key={`${change.channel}:${change.key}`} className="px-4 py-2">
            <div className="text-xs text-[var(--text-secondary)]">{change.channel} · <span className="font-mono">{change.key}</span></div>
            <div className="mt-1 break-all font-mono text-xs text-[var(--text-primary)]">{summarize(change.after, 220)}</div>
          </div>
        ))}
      </div>
    </section>
  )
}
