"use client"
import React, { use, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { AlertTriangle, ArrowLeft, ArrowRight, Play, Square } from 'lucide-react'
import {
  labService, Arm, CaseSummary, Experiment, ExperimentMetrics, LabStreamEvent, LiveEvent, RateWithCI,
  Topology, Verdict, armName, containmentLabel, deriveRoute, describeEvent, formatRate,
  FAMILY_LABELS, MECHANISM_LABELS, OBJECTIVE_LABELS, OUTCOME_LABELS,
} from '@/lib/lab-service'
import {
  CHANNEL_ICONS, CHANNEL_NAMES, ObjectiveGlyph, PropagationStage, RouteAxis, RouteLegend, RouteStrip, SealGlyph,
} from '@/components/LabRoute'
import { TableSkeleton } from '@/components/Skeletons'

type Phase = 'queued' | 'baseline' | 'attack' | 'done' | 'failed' | 'interrupted'

interface Pair {
  pairId: string
  caseId: string
  rep: number
  phase: Phase
  attackRunId: string | null
  /** The attack run's trace, kept once it streamed so the strip shows the
   *  edges it actually crossed rather than the ones its verdict implies. */
  events: LiveEvent[]
  verdict: Verdict | null
  reason: string | null
  /** The verdict arrived on this page's stream: animate it in. */
  fresh: boolean
}

interface LiveRun {
  runId: string
  pairId: string
  mode: 'CLEAN' | 'ATTACK'
  events: LiveEvent[]
}

interface Board {
  pairs: Record<string, Pair>
  order: string[]
  current: LiveRun | null
  /** The attack run on the stage: the one executing, else the last to finish. */
  stage: { pairId: string; runId: string; events: LiveEvent[]; verdict: Verdict | null } | null
  progress: { completed: number; total: number }
  rescored: Record<string, number>
}

const DEFAULT_PATH = ['A', 'B', 'C']

function boardFrom(experiment: Experiment, previous?: Board): Board {
  const config = experiment.config as { cases?: string[]; repetitions?: number }
  const pairs: Record<string, Pair> = {}
  const order: string[] = []
  for (const caseId of config.cases ?? []) {
    for (let rep = 1; rep <= (config.repetitions ?? 1); rep++) {
      const pairId = `${experiment.experiment_id}-${caseId}-r${rep}`
      order.push(pairId)
      pairs[pairId] = { pairId, caseId, rep, phase: 'queued', attackRunId: null, events: [], verdict: null, reason: null, fresh: false }
    }
  }

  // A resumed pair has rows from every attempt; a completed attack run wins,
  // then a failure, then a run left RUNNING by an interrupted stream.
  const rank: Record<Phase, number> = { done: 3, failed: 2, interrupted: 1, queued: 0, baseline: 0, attack: 0 }
  for (const run of experiment.runs ?? []) {
    const pair = pairs[run.pair_id]
    if (!pair) continue
    const phase: Phase =
      run.status === 'COMPLETED' ? (run.mode === 'ATTACK' ? 'done' : 'queued')
        : run.status === 'FAILED' ? 'failed'
          : run.status === 'RUNNING' ? 'interrupted' : 'queued'
    if (rank[phase] < rank[pair.phase]) continue
    pair.phase = phase
    if (run.mode === 'ATTACK') pair.attackRunId = run.run_id
    pair.verdict = phase === 'done' ? run.verdict : pair.verdict
    pair.reason = phase === 'failed' ? run.invalid_reason : pair.reason
  }

  for (const pairId of order) {
    const before = previous?.pairs[pairId]
    const pair = pairs[pairId]
    if (before && before.attackRunId === pair.attackRunId) {
      pair.events = before.events
      pair.fresh = before.fresh
    }
  }

  const done = order.filter((id) => pairs[id].phase === 'done').length
  return {
    pairs, order,
    current: null,
    stage: previous?.stage ?? null,
    progress: { completed: 2 * done, total: 2 * order.length },
    rescored: previous?.rescored ?? {},
  }
}

/** One stream event applied to the board. Pure, so a whole animation
 *  frame's worth of events folds in one state update. */
function applyEvent(board: Board, event: LabStreamEvent): Board {
  switch (event.event) {
    case 'experiment_started':
      return { ...board, progress: { completed: 2 * event.data.already_completed_pairs, total: event.data.total_runs } }

    case 'run_started': {
      const { run_id, pair_id, mode } = event.data
      const pair = board.pairs[pair_id]
      if (!pair) return board
      const attack = mode === 'ATTACK'
      return {
        ...board,
        pairs: { ...board.pairs, [pair_id]: { ...pair, phase: attack ? 'attack' : 'baseline', attackRunId: attack ? run_id : pair.attackRunId, verdict: null, fresh: false } },
        current: { runId: run_id, pairId: pair_id, mode: attack ? 'ATTACK' : 'CLEAN', events: [] },
        stage: attack ? { pairId: pair_id, runId: run_id, events: [], verdict: null } : board.stage,
      }
    }

    case 'trace_event': {
      const { run_id, ...live } = event.data
      if (board.current?.runId !== run_id) return board
      const events = [...board.current.events, live]
      return {
        ...board,
        current: { ...board.current, events },
        stage: board.stage?.runId === run_id ? { ...board.stage, events } : board.stage,
      }
    }

    case 'run_verdict': {
      const { run_id, pair_id, status, verdict, progress } = event.data
      const pair = board.pairs[pair_id]
      if (!pair) return board
      const events = board.current?.runId === run_id ? board.current.events : pair.events
      const failed = status !== 'COMPLETED'
      return {
        ...board,
        progress,
        pairs: {
          ...board.pairs,
          [pair_id]: { ...pair, phase: failed ? 'failed' : 'done', verdict: failed ? null : verdict, events, fresh: true, reason: failed ? 'harness error' : null },
        },
        current: null,
        stage: board.stage?.runId === run_id ? { ...board.stage, events, verdict: failed ? null : verdict } : board.stage,
      }
    }

    case 'case_rescored': {
      const pairs = { ...board.pairs }
      for (const { run_id, verdict } of event.data.runs) {
        const id = board.order.find((pid) => pairs[pid].attackRunId === run_id)
        if (id) pairs[id] = { ...pairs[id], verdict }
      }
      return { ...board, pairs, rescored: { ...board.rescored, [event.data.case_id]: event.data.baseline_runs } }
    }

    default:
      return board
  }
}

function stopped(board: Board): Board {
  const pairs = { ...board.pairs }
  for (const id of board.order) {
    if (pairs[id].phase === 'baseline' || pairs[id].phase === 'attack') pairs[id] = { ...pairs[id], phase: 'interrupted' }
  }
  return { ...board, pairs, current: null }
}

export default function LabExperimentPage({ params }: { params: Promise<{ experimentId: string }> }) {
  const { experimentId } = use(params)

  const [experiment, setExperiment] = useState<Experiment | null>(null)
  const [metrics, setMetrics] = useState<ExperimentMetrics | null>(null)
  const [cases, setCases] = useState<Record<string, CaseSummary>>({})
  const [topology, setTopology] = useState<Topology | null>(null)
  const [arm, setArm] = useState<Arm | null>(null)
  const [board, setBoard] = useState<Board | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const sourceRef = useRef<EventSource | null>(null)
  const completedRef = useRef(false)
  const queueRef = useRef<LabStreamEvent[]>([])
  const frameRef = useRef<number | null>(null)
  const autoRef = useRef(false)

  const refresh = useCallback(async () => {
    const [exp, met] = await Promise.all([
      labService.fetchExperiment(experimentId),
      labService.fetchMetrics(experimentId).catch(() => null),
    ])
    setExperiment(exp)
    setMetrics(met)
    setBoard((prev) => boardFrom(exp, prev ?? undefined))
    return exp
  }, [experimentId])

  // The stream is the one endpoint that spends model budget; leaving the
  // page must stop it.
  useEffect(() => () => {
    sourceRef.current?.close()
    if (frameRef.current !== null) cancelAnimationFrame(frameRef.current)
  }, [])

  const flush = useCallback(() => {
    frameRef.current = null
    const batch = queueRef.current
    queueRef.current = []
    setBoard((prev) => (prev ? batch.reduce(applyEvent, prev) : prev))
  }, [])

  const onStreamEvent = useCallback((event: LabStreamEvent) => {
    if (event.event === 'experiment_complete') {
      completedRef.current = true
      sourceRef.current?.close()
      setRunning(false)
      flush()
      refresh().catch(() => undefined)
      return
    }
    if (event.event === 'experiment_error') {
      completedRef.current = true
      sourceRef.current?.close()
      setRunning(false)
      setError(event.data.error)
      return
    }
    queueRef.current.push(event)
    if (frameRef.current === null) frameRef.current = requestAnimationFrame(flush)
  }, [flush, refresh])

  const start = useCallback(() => {
    setError(null)
    completedRef.current = false
    setRunning(true)
    sourceRef.current = labService.streamExperiment(experimentId, onStreamEvent, () => {
      // Closing matters: an open EventSource reconnects by itself, and the
      // server resumes the experiment on every reconnect.
      sourceRef.current?.close()
      setRunning(false)
      if (!completedRef.current) {
        flush()
        setBoard((prev) => (prev ? stopped(prev) : prev))
        setError('The stream closed before the experiment finished. Completed pairs are saved; Resume continues from the first unfinished one.')
      }
    })
  }, [experimentId, onStreamEvent, flush])

  const stop = () => {
    completedRef.current = true
    sourceRef.current?.close()
    setRunning(false)
    flush()
    setBoard((prev) => (prev ? stopped(prev) : prev))
  }

  useEffect(() => {
    Promise.all([
      labService.fetchExperiment(experimentId),
      labService.fetchMetrics(experimentId).catch(() => null),
      labService.fetchCases(),
      labService.fetchTopologies(),
      labService.fetchArms(),
    ])
      .then(([exp, met, caseList, topologies, arms]) => {
        setExperiment(exp)
        setMetrics(met)
        setBoard((prev) => boardFrom(exp, prev ?? undefined))
        setCases(Object.fromEntries(caseList.map((c) => [c.id, c])))
        setTopology(topologies.topologies.find((t) => t.id === (exp.config as { topology_id?: string }).topology_id) ?? topologies.topologies[0] ?? null)
        setArm(arms.find((a) => a.key === exp.arm) ?? null)
        // Launched from /lab with ?run=1: start once, then drop the flag so a
        // reload shows the board instead of spending more model calls.
        if (!autoRef.current && new URLSearchParams(window.location.search).get('run') === '1') {
          autoRef.current = true
          window.history.replaceState(null, '', window.location.pathname)
          start()
        }
      })
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false))
  }, [experimentId, start])

  if (loading) return <TableSkeleton />

  if (!experiment || !board) {
    return (
      <div className="space-y-4">
        <BackLink />
        <ErrorLine message={error ?? 'Experiment not found'} />
      </div>
    )
  }

  const config = experiment.config as { model?: { provider?: string; model?: string }; scripted?: boolean; max_steps?: number; repetitions?: number; cases?: string[] }
  const unfinished = board.order.some((id) => board.pairs[id].phase !== 'done')
  const current = board.current
  const currentPair = current ? board.pairs[current.pairId] : null
  const stageCase = board.stage ? cases[board.pairs[board.stage.pairId]?.caseId] : null

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 border-b border-[var(--border-subtle)] pb-5 md:flex-row md:items-end md:justify-between">
        <div className="min-w-0">
          <BackLink />
          <h1 className="mt-2 text-2xl font-bold tracking-tight text-[var(--text-primary)]">{experiment.name}</h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            <span className="font-semibold text-[var(--text-primary)]">{armName(experiment.arm)}</span>
            {' · '}{config.scripted ? 'scripted replay, no model calls' : <span className="font-mono">{config.model?.provider} / {config.model?.model}</span>}
            {' · '}{config.max_steps ?? '—'} steps per agent · {config.cases?.length ?? 0} cases × {config.repetitions ?? 1} repetitions
          </p>
          {arm && <p className="mt-1 max-w-3xl text-xs text-[var(--text-secondary)]">{arm.description}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {running ? (
            <button onClick={stop} className="inline-flex items-center gap-1.5 rounded-[var(--radius)] border border-[var(--border-default)] bg-[var(--surface-raised)] px-3 py-2 text-sm font-semibold text-[var(--text-primary)] hover:border-[var(--text-secondary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--primary)]">
              <Square className="h-3.5 w-3.5" /> Stop
            </button>
          ) : unfinished ? (
            <button onClick={start} className="inline-flex items-center gap-1.5 rounded-[var(--radius)] bg-[var(--primary)] px-3 py-2 text-sm font-semibold text-[var(--primary-foreground)] hover:bg-[var(--primary-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]">
              <Play className="h-3.5 w-3.5" /> {board.progress.completed > 0 ? 'Resume' : 'Run'}
            </button>
          ) : null}
        </div>
      </header>

      {error && <ErrorLine message={error} />}

      <Instrument board={board} running={running} />

      {(running || board.stage) && (
        <section aria-label="Live propagation" className="rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)]">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border-subtle)] px-4 py-2.5 text-sm">
            <NowLine current={current} currentPair={currentPair} running={running} stagePair={board.stage ? board.pairs[board.stage.pairId] : null} />
            {board.stage?.verdict && !running && board.pairs[board.stage.pairId]?.attackRunId && (
              <Link href={`/lab/runs/${board.stage.runId}`} className="inline-flex items-center gap-1 text-sm font-semibold text-[var(--primary)] hover:underline">
                Replay <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            )}
          </div>
          <div className="overflow-x-auto px-4 py-4">
            {board.stage && stageCase ? (
              <PropagationStage
                path={stageCase.expected_path}
                entry={stageCase.injection_point}
                channel={stageCase.channel}
                eligible={stageCase.eligible_downstream_agents}
                route={deriveRoute(board.stage.events, stageCase.expected_path)}
                verdict={board.stage.verdict}
                location={plantedLocation(board.stage.events)}
                toolAuth={topology?.tool_auth}
                live
              />
            ) : (
              <p className="py-10 text-center text-sm text-[var(--text-secondary)]">Waiting for the first attack run. Its clean baseline runs first.</p>
            )}
          </div>
        </section>
      )}

      <Ledger board={board} cases={cases} running={running} />

      {metrics && metrics.n_attack_runs > 0 && <Rates metrics={metrics} />}

      <Containment board={board} />

      {metrics && Object.keys(metrics.per_case).length > 0 && <PerCase metrics={metrics} />}

      <Reproducibility experiment={experiment} />
    </div>
  )
}

function plantedLocation(events: LiveEvent[]): string | null {
  const planted = events.find((e) => e.event_type === 'artifact_planted')
  const location = planted?.resource?.location
  return typeof location === 'string' ? location : null
}

function BackLink() {
  return (
    <Link href="/lab" className="inline-flex items-center gap-1 text-sm font-semibold text-[var(--primary)] hover:underline">
      <ArrowLeft className="h-3.5 w-3.5" /> Lab
    </Link>
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

// ─────────────────────────────────────────────────────────────────────────────
// Instrument line — progress and the running tally, glyphs doubling as legend
// ─────────────────────────────────────────────────────────────────────────────

function tally(board: Board) {
  const t = { reached: 0, partial: 0, held: 0, invalid: 0, failed: 0, notContained: 0, local: 0, sealed: {} as Record<string, number> }
  for (const id of board.order) {
    const pair = board.pairs[id]
    if (pair.phase === 'failed') t.failed += 1
    const v = pair.verdict
    if (pair.phase !== 'done' || !v) continue
    if (v.system_outcome === 'RUN_INVALID') {
      t.invalid += 1
      continue
    }
    const level = v.objective.level
    if (level === 'REACHED' || level === 'CRITICAL_REACHED') t.reached += 1
    else if (level === 'PARTIALLY_REACHED') t.partial += 1
    else t.held += 1
    if (v.containment.status === 'CONTAINED' && v.containment.agent) t.sealed[v.containment.agent] = (t.sealed[v.containment.agent] ?? 0) + 1
    else if (v.containment.status === 'NO_DOWNSTREAM_ELIGIBLE') t.local += 1
    else t.notContained += 1
  }
  return t
}

function Instrument({ board, running }: { board: Board; running: boolean }) {
  const t = tally(board)
  const { completed, total } = board.progress
  const reduced = useReducedMotion()
  const agents = Array.from(new Set([...DEFAULT_PATH, ...Object.keys(t.sealed)])).sort()
  const cell = 'flex items-center gap-1.5 whitespace-nowrap'
  const num = 'font-mono text-sm font-semibold tabular-nums text-[var(--text-primary)]'

  return (
    <section aria-label="Progress" className="rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)] px-4 py-3">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3 text-sm text-[var(--text-secondary)]">
        <div className="flex min-w-[12rem] flex-1 items-center gap-3">
          {running && (
            <span className="relative flex h-2.5 w-2.5 shrink-0" aria-hidden>
              {!reduced && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--primary)] opacity-60" />}
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-[var(--primary)]" />
            </span>
          )}
          <span className="whitespace-nowrap"><span className={num}>{completed}</span> / {total} runs</span>
          <div className="h-1.5 min-w-[6rem] flex-1 overflow-hidden rounded-full bg-[var(--surface-base)]" role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={completed}>
            <motion.div className="h-full rounded-full bg-[var(--primary)]" initial={false} animate={{ width: total ? `${(completed / total) * 100}%` : '0%' }} transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }} />
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <span className={cell}><ObjectiveGlyph level="REACHED" /><span className={num}>{t.reached}</span> reached</span>
          <span className={cell}><ObjectiveGlyph level="PARTIALLY_REACHED" /><span className={num}>{t.partial}</span> partial</span>
          <span className={cell}><ObjectiveGlyph level="NOT_REACHED" /><span className={num}>{t.held}</span> not reached</span>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <span className={cell}><SealGlyph /> sealed at {agents.map((a, i) => (
            <span key={a}>{i > 0 && ' · '}{a} <span className={num}>{t.sealed[a] ?? 0}</span></span>
          ))}</span>
          <span className={cell}><span className={num}>{t.notContained}</span> not contained</span>
          {t.local > 0 && <span className={cell}><span className={num}>{t.local}</span> entry-local</span>}
        </div>
        {(t.invalid > 0 || t.failed > 0) && (
          <div className="flex items-center gap-x-4">
            {t.invalid > 0 && <span className={cell} title="The paired clean run did not complete the task, so the pair is left out of every rate"><span className={num}>{t.invalid}</span> invalid</span>}
            {t.failed > 0 && <span className={cell} title="A run hit a harness error; the pair re-runs on resume"><AlertTriangle className="h-3.5 w-3.5 text-[var(--danger)]" /><span className={num}>{t.failed}</span> failed</span>}
          </div>
        )}
      </div>
    </section>
  )
}

function NowLine({ current, currentPair, running, stagePair }: {
  current: LiveRun | null; currentPair: Pair | null; running: boolean; stagePair: Pair | null
}) {
  const last = current?.events[current.events.length - 1]
  let text: React.ReactNode
  if (running && current && currentPair) {
    text = (
      <>
        <span className="font-mono font-semibold text-[var(--text-primary)]">{currentPair.caseId}</span>
        <span className="text-[var(--text-secondary)]"> rep {currentPair.rep} · {current.mode === 'CLEAN' ? 'clean baseline' : 'attack run'}</span>
        {last && <span className="ml-2 font-mono text-[var(--text-primary)]">{describeEvent(last)}</span>}
      </>
    )
  } else if (running) {
    text = <span className="text-[var(--text-secondary)]">Starting…</span>
  } else if (stagePair) {
    text = (
      <>
        <span className="text-[var(--text-secondary)]">Last attack run · </span>
        <span className="font-mono font-semibold text-[var(--text-primary)]">{stagePair.caseId}</span>
        <span className="text-[var(--text-secondary)]"> rep {stagePair.rep}</span>
      </>
    )
  }
  return (
    <div className="min-w-0 truncate" aria-live="polite">
      <AnimatePresence mode="popLayout" initial={false}>
        <motion.span key={last?.step ?? current?.runId ?? 'idle'} className="inline" initial={{ opacity: 0.4 }} animate={{ opacity: 1 }} transition={{ duration: 0.15 }}>
          {text}
        </motion.span>
      </AnimatePresence>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// The propagation ledger
// ─────────────────────────────────────────────────────────────────────────────

function Ledger({ board, cases, running }: { board: Board; cases: Record<string, CaseSummary>; running: boolean }) {
  const groups = useMemo(() => {
    const byCase: { caseId: string; pairs: string[] }[] = []
    for (const id of board.order) {
      const caseId = board.pairs[id].caseId
      const group = byCase[byCase.length - 1]
      if (group?.caseId === caseId) group.pairs.push(id)
      else byCase.push({ caseId, pairs: [id] })
    }
    return byCase
  }, [board.order, board.pairs])

  const path = Object.values(cases)[0]?.expected_path ?? DEFAULT_PATH

  return (
    <section aria-label="Every attack run" className="overflow-hidden rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)]">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border-subtle)] px-4 py-3">
        <h2 className="text-base font-semibold text-[var(--text-primary)]">Every attack run</h2>
        <RouteLegend />
      </div>

      <div className="hidden items-end gap-4 border-b-2 border-[var(--border-default)] bg-[var(--surface-base)] px-4 py-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-secondary)] lg:grid lg:grid-cols-[3rem_224px_minmax(9rem,1fr)_minmax(8rem,0.8fr)_minmax(9rem,1fr)_1.25rem]">
        <span>Rep</span>
        <RouteAxis path={path} />
        <span>Containment</span>
        <span>Objective</span>
        <span>Task</span>
        <span />
      </div>

      {groups.map(({ caseId, pairs }) => {
        const c = cases[caseId]
        const Icon = c ? CHANNEL_ICONS[c.channel] : null
        return (
          <div key={caseId} className="border-b border-[var(--border-subtle)] last:border-b-0">
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 bg-[var(--surface-base)] px-4 py-2">
              <span className="font-mono text-sm font-bold text-[var(--text-primary)]">{caseId}</span>
              {c && <span className="text-sm text-[var(--text-primary)]">{c.title}</span>}
              {c && (
                <span className="inline-flex items-center gap-1.5 text-xs text-[var(--text-secondary)]">
                  {FAMILY_LABELS[c.family] ?? c.family} ·{Icon && <Icon className="h-3.5 w-3.5" aria-hidden />}
                  enters via {CHANNEL_NAMES[c.channel] ?? c.channel} at {c.injection_point}
                </span>
              )}
              {board.rescored[caseId] && (
                <span className="text-xs text-[var(--text-secondary)]" title="Every verdict of this case was re-judged against all of its clean repetitions, not only its own pair">
                  · judged against {board.rescored[caseId]} clean runs
                </span>
              )}
            </div>
            <ol>
              {pairs.map((id) => (
                <PairRow key={id} pair={board.pairs[id]} c={c} live={running && board.current?.pairId === id} liveEvents={board.current?.pairId === id && board.current.mode === 'ATTACK' ? board.current.events : null} />
              ))}
            </ol>
          </div>
        )
      })}
    </section>
  )
}

const PairRow = React.memo(function PairRow({ pair, c, live, liveEvents }: {
  pair: Pair; c?: CaseSummary; live: boolean; liveEvents: LiveEvent[] | null
}) {
  const path = c?.expected_path ?? DEFAULT_PATH
  const events = liveEvents ?? pair.events
  const route = events.length ? deriveRoute(events, path) : null
  const v = pair.verdict
  const settled = pair.phase === 'done' && v
  const linkable = (pair.phase === 'done' || pair.phase === 'failed') && pair.attackRunId

  const body = (
    <>
      <span className="font-mono text-sm tabular-nums text-[var(--text-secondary)]">#{pair.rep}</span>
      <span className={pair.phase === 'queued' || pair.phase === 'interrupted' ? 'opacity-50' : ''}>
        {c && (
          <RouteStrip path={path} entry={c.injection_point} channel={c.channel} eligible={c.eligible_downstream_agents}
            route={route} verdict={settled ? v : null} live={pair.fresh || live} />
        )}
      </span>
      {settled ? (
        // One wrapped line under the strip on narrow screens; `contents` on
        // desktop hands the three cells back to the row's grid columns.
        <div className="col-start-2 flex min-w-0 flex-wrap items-baseline gap-x-4 gap-y-1 lg:contents">
          <span className="min-w-0 text-sm">
            <span className="font-semibold text-[var(--text-primary)]">{containmentLabel(v)}</span>
            {v.containment.mechanism && (
              <span className="block truncate text-xs text-[var(--text-secondary)]">{MECHANISM_LABELS[v.containment.mechanism] ?? v.containment.mechanism}</span>
            )}
          </span>
          <motion.span className="inline-flex items-center gap-1.5 text-sm text-[var(--text-primary)]"
            initial={pair.fresh ? { opacity: 0, y: 3 } : false} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}>
            <ObjectiveGlyph level={v.objective.level} />
            {OBJECTIVE_LABELS[v.objective.level]}
          </motion.span>
          <span className={`text-sm ${v.system_outcome === 'RUN_INVALID' || v.system_outcome === 'TASK_FAILED' ? 'text-[var(--text-primary)]' : 'text-[var(--text-secondary)]'}`}>
            {v.system_outcome === 'RUN_INVALID' && <AlertTriangle className="mr-1 inline h-3.5 w-3.5 text-[var(--warning)]" aria-hidden />}
            {OUTCOME_LABELS[v.system_outcome]}
          </span>
        </div>
      ) : (
        <span className="col-start-2 min-w-0 text-sm text-[var(--text-secondary)] lg:col-span-3 lg:col-start-auto">
          <PhaseLine pair={pair} live={live} lastEvent={liveEvents?.[liveEvents.length - 1] ?? null} />
        </span>
      )}
      <span className="hidden justify-self-end lg:block">{linkable && <ArrowRight className="h-4 w-4 text-[var(--text-secondary)]" aria-hidden />}</span>
    </>
  )

  const row = `grid grid-cols-[2.5rem_1fr] items-center gap-x-4 gap-y-1.5 px-4 py-2.5 lg:grid-cols-[3rem_224px_minmax(9rem,1fr)_minmax(8rem,0.8fr)_minmax(9rem,1fr)_1.25rem] ${live ? 'bg-[color-mix(in_srgb,var(--primary)_7%,transparent)]' : ''}`

  return (
    <li className="border-t border-[var(--border-subtle)] first:border-t-0">
      {linkable ? (
        <Link href={`/lab/runs/${pair.attackRunId}`} className={`${row} transition-colors hover:bg-[color-mix(in_srgb,var(--primary)_6%,transparent)] focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--primary)]`}
          aria-label={`${pair.caseId} repetition ${pair.rep}: open the replay`}>
          {body}
        </Link>
      ) : (
        <div className={row}>{body}</div>
      )}
    </li>
  )
})

function PhaseLine({ pair, live, lastEvent }: { pair: Pair; live: boolean; lastEvent: LiveEvent | null }) {
  switch (pair.phase) {
    case 'baseline':
      return <span><span className="font-semibold text-[var(--text-primary)]">Clean baseline running</span> · the control this attack run is judged against</span>
    case 'attack':
      return (
        <span className="font-mono text-[var(--text-primary)]">
          {live && lastEvent ? describeEvent(lastEvent) : 'Attack run starting'}
        </span>
      )
    case 'failed':
      return (
        <span className="inline-flex items-center gap-1.5">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-[var(--danger)]" aria-hidden />
          <span className="text-[var(--text-primary)]">Harness error</span>
          {pair.reason && <span className="truncate font-mono text-xs">{pair.reason}</span>}
          <span>· excluded, re-runs on resume</span>
        </span>
      )
    case 'interrupted':
      return <span>Interrupted · re-runs on resume</span>
    default:
      return <span>Queued</span>
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Rates, containment, per case, reproducibility
// ─────────────────────────────────────────────────────────────────────────────

function IntervalBar({ rate }: { rate: RateWithCI }) {
  if (rate.value === null || !rate.ci) return <span className="text-sm text-[var(--text-secondary)]">—</span>
  const [lo, hi] = rate.ci
  const pct = (x: number) => `${(x * 100).toFixed(0)}%`
  return (
    <div className="flex items-center gap-3">
      <div className="relative h-4 min-w-[8rem] flex-1" role="img" aria-label={`${pct(rate.value)}, 95% interval ${pct(lo)} to ${pct(hi)}`}>
        <div className="absolute inset-x-0 top-1/2 h-px bg-[var(--border-default)]" />
        {[0, 0.5, 1].map((tick) => (
          <div key={tick} className="absolute top-1/2 h-2 w-px -translate-y-1/2 bg-[var(--border-default)]" style={{ left: `${tick * 100}%` }} />
        ))}
        <div className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-[var(--accent)]" style={{ left: `${lo * 100}%`, width: `${Math.max(0.6, (hi - lo) * 100)}%` }} />
        <div className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-[var(--surface-raised)] bg-[var(--text-primary)]" style={{ left: `${rate.value * 100}%` }} />
      </div>
      <span className="whitespace-nowrap font-mono text-xs tabular-nums text-[var(--text-secondary)]">{pct(lo)}–{pct(hi)}</span>
    </div>
  )
}

function sampleNote(rate: RateWithCI): string {
  if (!rate.n) return 'no valid runs'
  if (rate.ci_method !== 'wilson_design_effect' || rate.n_eff == null) return `${rate.n} runs of one case`
  const cases = `${rate.n_cases} cases`
  if (rate.n_eff >= rate.n - 0.5) return `${rate.n} runs, ${cases}; runs look independent`
  const worth = rate.n_eff < 10 ? String(Number(rate.n_eff.toFixed(1))) : String(Math.round(rate.n_eff))
  return `${rate.n} runs, ${cases}; worth about ${worth} independent`
}

function Rates({ metrics }: { metrics: ExperimentMetrics }) {
  const a = metrics.aggregate
  const rows: { label: string; hint: string; rate: RateWithCI }[] = [
    { label: 'Entry agent compromised', hint: 'ICR', rate: a.icr },
    { label: 'Objective reached', hint: 'ASR', rate: a.asr },
    { label: 'Objective partially reached', hint: 'partial', rate: a.partial_rate },
  ]
  return (
    <section aria-label="Rates" className="overflow-hidden rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)]">
      <div className="border-b border-[var(--border-subtle)] px-4 py-3">
        <h2 className="text-base font-semibold text-[var(--text-primary)]">Rates</h2>
        <p className="mt-0.5 max-w-3xl text-xs text-[var(--text-secondary)]">
          Runs of one case succeed or fail together, so each interval is computed over the effective number of
          independent observations, not over the raw run count.
          {metrics.n_failed_pairs > 0 && ` ${metrics.n_failed_pairs} pair(s) hit a harness error and are left out of every rate.`}
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="research-table">
          <thead>
            <tr>
              <th>Measure</th>
              <th className="text-right">Rate</th>
              <th className="w-[40%]">95% interval</th>
              <th>Sample</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ label, hint, rate }) => (
              <tr key={hint}>
                <td>{label} <span className="text-xs text-[var(--text-secondary)]">{hint}</span></td>
                <td className="text-right font-mono tabular-nums">{formatRate(rate.value)}</td>
                <td><IntervalBar rate={rate} /></td>
                <td className="text-sm text-[var(--text-secondary)]">{sampleNote(rate)}</td>
              </tr>
            ))}
            <tr>
              <td>Propagated past a compromised entry <span className="text-xs text-[var(--text-secondary)]">CPR</span></td>
              <td className="text-right font-mono tabular-nums">{formatRate(a.cpr)}</td>
              <td className="text-sm text-[var(--text-secondary)]">
                {a.cpr === 'n/a' ? 'Undefined, not 0%: no run compromised an entry agent that had anywhere to propagate to.' : 'No interval: the denominator is itself an outcome.'}
              </td>
              <td className="text-sm text-[var(--text-secondary)]">{a.cpr_denominator_size} eligible runs</td>
            </tr>
            <tr>
              <td>Contained <span className="text-xs text-[var(--text-secondary)]">of runs with downstream agents</span></td>
              <td className="text-right font-mono tabular-nums">{formatRate(a.containment_rate)}</td>
              <td className="text-sm text-[var(--text-secondary)]">Where, and by what, is below.</td>
              <td className="text-sm text-[var(--text-secondary)]">{a.mean_coverage === null ? 'no propagating runs' : `mean coverage ${formatRate(a.mean_coverage)}`}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  )
}

function Containment({ board }: { board: Board }) {
  const rows = useMemo(() => {
    const sealed: Record<string, Record<string, number>> = {}
    let notContained = 0
    let local = 0
    let valid = 0
    for (const id of board.order) {
      const v = board.pairs[id].verdict
      if (board.pairs[id].phase !== 'done' || !v || v.system_outcome === 'RUN_INVALID') continue
      valid += 1
      const c = v.containment
      if (c.status === 'CONTAINED' && c.agent) {
        const byMechanism = (sealed[c.agent] ??= {})
        byMechanism[c.mechanism ?? 'unknown'] = (byMechanism[c.mechanism ?? 'unknown'] ?? 0) + 1
      } else if (c.status === 'NO_DOWNSTREAM_ELIGIBLE') local += 1
      else notContained += 1
    }
    return { sealed, notContained, local, valid }
  }, [board.order, board.pairs])

  if (rows.valid === 0) return null
  const agents = Object.keys(rows.sealed).sort()
  const share = (n: number) => `${(n / rows.valid) * 100}%`
  const line = (label: React.ReactNode, count: number, color: string, detail?: React.ReactNode) => (
    <div className="grid grid-cols-[9rem_2.5rem_1fr] items-center gap-3 py-1.5 sm:grid-cols-[10rem_2.5rem_minmax(6rem,14rem)_1fr]">
      <span className="text-sm text-[var(--text-primary)]">{label}</span>
      <span className="text-right font-mono text-sm font-semibold tabular-nums text-[var(--text-primary)]">{count}</span>
      <span className="h-2 rounded-sm bg-[var(--surface-base)]">
        <span className="block h-2 rounded-sm" style={{ width: share(count), background: color }} />
      </span>
      <span className="col-span-3 text-xs text-[var(--text-secondary)] sm:col-span-1">{detail}</span>
    </div>
  )

  return (
    <section aria-label="Where attacks stopped" className="rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)] px-4 py-3">
      <h2 className="text-base font-semibold text-[var(--text-primary)]">Where attacks stopped</h2>
      <p className="mt-0.5 mb-2 text-xs text-[var(--text-secondary)]">{rows.valid} valid attack runs. The mechanism is the finding: which control, not just whether.</p>
      <div className="divide-y divide-[var(--border-subtle)]">
        {agents.map((agent) => {
          const byMechanism = rows.sealed[agent]
          const total = Object.values(byMechanism).reduce((x, y) => x + y, 0)
          return (
            <React.Fragment key={agent}>
              {line(
                <span className="inline-flex items-center gap-1.5"><SealGlyph /> Sealed at {agent}</span>,
                total, 'var(--success)',
                Object.entries(byMechanism).map(([m, n]) => `${MECHANISM_LABELS[m] ?? m} ${n}`).join(' · '),
              )}
            </React.Fragment>
          )
        })}
        {line('Not contained', rows.notContained, 'var(--danger)', 'the compromise chain reached every eligible agent')}
        {rows.local > 0 && line('Entry-local', rows.local, 'var(--text-muted)', 'no downstream agent was eligible, so containment does not apply')}
      </div>
    </section>
  )
}

function PerCase({ metrics }: { metrics: ExperimentMetrics }) {
  return (
    <section aria-label="Per case" className="overflow-hidden rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)]">
      <div className="border-b border-[var(--border-subtle)] px-4 py-3">
        <h2 className="text-base font-semibold text-[var(--text-primary)]">Per case</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="research-table">
          <thead>
            <tr>
              <th>Case</th>
              <th className="text-right">Runs</th>
              <th className="text-right">ICR</th>
              <th className="text-right">ASR</th>
              <th className="text-right">CPR</th>
              <th className="text-right">Consistency</th>
              <th className="text-right">Drift vs noise</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(metrics.per_case).map(([caseId, s]) => {
              const drift = metrics.trajectory_drift[caseId]
              return (
                <tr key={caseId}>
                  <td className="font-mono font-semibold">{caseId}</td>
                  <td className="text-right font-mono tabular-nums">{s.n}</td>
                  <td className="text-right font-mono tabular-nums">{formatRate(s.icr)}</td>
                  <td className="text-right font-mono tabular-nums">{formatRate(s.asr)}</td>
                  <td className="text-right font-mono tabular-nums">{formatRate(s.cpr)}</td>
                  <td className="text-right font-mono tabular-nums">
                    {s.soc === null ? <span className="text-[var(--text-secondary)]" title="Needs at least 3 repetitions">N&lt;3</span> : s.soc.toFixed(2)}
                  </td>
                  <td className="text-right font-mono text-sm tabular-nums">
                    {!drift || !drift.interpretable
                      ? <span className="text-[var(--text-secondary)]" title="No clean-vs-clean noise floor: needs at least 2 clean repetitions">no noise floor</span>
                      : `${drift.attack?.toFixed(2)} vs ${drift.null?.toFixed(2)}`}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="border-t border-[var(--border-subtle)] px-4 py-2 text-xs text-[var(--text-secondary)]">
        CPR is n/a when no run compromised the entry agent: the question was never asked, which is not the same as
        propagation never happening. Drift only means something against the clean-vs-clean noise floor beside it.
      </p>
    </section>
  )
}

function Reproducibility({ experiment }: { experiment: Experiment }) {
  const versions = experiment.versions?.versions ?? {}
  return (
    <details className="rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)] px-4 py-3">
      <summary className="cursor-pointer text-sm font-semibold text-[var(--text-primary)]">Reproducibility stamp</summary>
      <dl className="mt-3 grid gap-x-8 gap-y-1 text-sm sm:grid-cols-2 lg:grid-cols-3">
        {Object.entries(versions).map(([key, value]) => (
          <div key={key} className="flex justify-between gap-3">
            <dt className="text-[var(--text-secondary)]">{key}</dt>
            <dd className="font-mono text-[var(--text-primary)]">{String(value)}</dd>
          </div>
        ))}
        <div className="flex justify-between gap-3">
          <dt className="text-[var(--text-secondary)]">git_commit</dt>
          <dd className="truncate font-mono text-[var(--text-primary)]">{String(experiment.versions?.git_commit ?? '—').slice(0, 12)}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-[var(--text-secondary)]">git_clean</dt>
          <dd className="font-mono text-[var(--text-primary)]">{String(experiment.versions?.git_clean ?? 'unknown')}</dd>
        </div>
      </dl>
    </details>
  )
}
