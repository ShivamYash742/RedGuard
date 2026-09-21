"use client"
import React, { useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import {
  FlaskConical, Play, Square, ArrowRight, Network, AlertTriangle, CheckCircle2, Loader2,
} from 'lucide-react'
import {
  labService, Arm, CaseSummary, Experiment, LabStreamEvent, Topology, Verdict,
  OBJECTIVE_STYLES,
} from '@/lib/lab-service'
import EmptyState from '@/components/EmptyState'
import { TableSkeleton } from '@/components/Skeletons'

interface LiveRun {
  runId: string
  caseId: string
  mode: string
  repetition: number
  events: number
  verdict?: Verdict
  status?: string
  /** A clean run finishes without a verdict of its own — it *is* the
   *  baseline. Tracked separately so it can stop showing as in-progress. */
  done?: boolean
}

const FAMILY_LABELS: Record<string, string> = {
  content_injection: 'Content injection',
  tool_manipulation: 'Tool manipulation',
  memory_poisoning: 'Memory poisoning',
  direct_injection: 'Direct injection',
}

export default function LabPage() {
  const [cases, setCases] = useState<CaseSummary[]>([])
  const [arms, setArms] = useState<Arm[]>([])
  const [topology, setTopology] = useState<Topology | null>(null)
  const [experiments, setExperiments] = useState<Experiment[]>([])
  const [loading, setLoading] = useState(true)

  const [selectedCases, setSelectedCases] = useState<string[]>([])
  const [arm, setArm] = useState('attack')
  const [repetitions, setRepetitions] = useState(5)
  const [provider, setProvider] = useState('ollama')
  const [model, setModel] = useState('')
  const [scripted, setScripted] = useState(true)

  const [running, setRunning] = useState(false)
  const [experimentId, setExperimentId] = useState<string | null>(null)
  const [progress, setProgress] = useState({ completed: 0, total: 0 })
  const [liveRuns, setLiveRuns] = useState<LiveRun[]>([])
  const [error, setError] = useState<string | null>(null)
  const sourceRef = useRef<EventSource | null>(null)

  useEffect(() => {
    Promise.all([
      labService.fetchCases(),
      labService.fetchArms(),
      labService.fetchTopologies(),
      labService.fetchExperiments(),
    ])
      .then(([caseList, armList, topologies, experimentList]) => {
        setCases(caseList)
        setSelectedCases(caseList.map((c) => c.id))
        setArms(armList)
        setTopology(topologies.topologies[0] ?? null)
        setExperiments(experimentList)
      })
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false))
  }, [])

  // The stream is the one endpoint that spends model budget, so an abandoned
  // page must not leave it running.
  useEffect(() => () => sourceRef.current?.close(), [])

  const totalRuns = selectedCases.length * repetitions * 2

  const toggleCase = (id: string) =>
    setSelectedCases((prev) => (prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]))

  const handleStreamEvent = (event: LabStreamEvent) => {
    switch (event.event) {
      case 'experiment_started':
        setProgress({ completed: 0, total: event.data.total_runs })
        break
      case 'run_started':
        setLiveRuns((prev) => [
          {
            runId: event.data.run_id,
            caseId: event.data.case_id,
            mode: event.data.mode,
            repetition: event.data.repetition_index,
            events: 0,
          },
          ...prev,
        ])
        break
      case 'trace_event':
        setLiveRuns((prev) =>
          prev.map((r) => (r.runId === event.data.run_id ? { ...r, events: r.events + 1 } : r)),
        )
        break
      case 'run_verdict':
        setProgress(event.data.progress)
        // One verdict event closes out *both* halves of the pair: the attack
        // run carries the verdict, and its clean baseline is finished too —
        // without this the clean rows spin forever, which reads as a stalled
        // run rather than a completed baseline.
        setLiveRuns((prev) =>
          prev.map((r) => {
            if (r.runId === event.data.run_id) {
              return { ...r, verdict: event.data.verdict, status: event.data.status, done: true }
            }
            if (r.runId === event.data.baseline_run_id) {
              return { ...r, status: event.data.status, done: true }
            }
            return r
          }),
        )
        break
      case 'experiment_complete':
        setRunning(false)
        sourceRef.current?.close()
        labService.fetchExperiments().then(setExperiments).catch(() => undefined)
        break
      case 'experiment_error':
        setError(event.data.error)
        setRunning(false)
        sourceRef.current?.close()
        break
    }
  }

  const launch = async () => {
    setError(null)
    setLiveRuns([])
    setProgress({ completed: 0, total: 0 })
    setRunning(true)
    try {
      const created = await labService.createExperiment({
        arm,
        cases: selectedCases,
        repetitions,
        provider,
        model: model || undefined,
        scripted,
      })
      setExperimentId(created.experiment_id)
      sourceRef.current = labService.streamExperiment(created.experiment_id, handleStreamEvent, () => {
        // EventSource fires onerror on normal stream end too, so this only
        // reports when nothing has completed — otherwise it is just the close.
        setRunning(false)
      })
    } catch (err) {
      setError(String(err))
      setRunning(false)
    }
  }

  const stop = () => {
    sourceRef.current?.close()
    setRunning(false)
  }

  const selectedFamilies = useMemo(() => {
    const counts: Record<string, number> = {}
    cases
      .filter((c) => selectedCases.includes(c.id))
      .forEach((c) => {
        counts[c.family] = (counts[c.family] ?? 0) + 1
      })
    return counts
  }, [cases, selectedCases])

  if (loading) return <TableSkeleton />

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="border-b border-[var(--border-subtle)] pb-4">
        <div className="flex items-center gap-2 text-xs font-semibold text-[var(--primary)] uppercase tracking-wider mb-1">
          <FlaskConical className="h-4 w-4" /> Multi-Agent Lab
        </div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-tight">
          Security Test Cases
        </h1>
        <p className="text-xs text-[var(--text-secondary)] mt-0.5 max-w-3xl">
          Mode B measures what a <em>system</em> of agents did after an attack entered it — which
          agent was influenced, how far it propagated, and where it was contained. Every event is
          observed by the harness rather than self-reported.
        </p>
      </div>

      {error && (
        <div className="flex items-start gap-2 p-3 rounded-[var(--radius)] border border-[var(--danger)]/30 bg-[var(--danger-bg)] text-xs text-[var(--danger)]">
          <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
          <span className="font-mono break-all">{error}</span>
        </div>
      )}

      {/* Topology */}
      {topology && (
        <section className="rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)] p-4">
          <div className="flex items-center gap-2 text-xs font-semibold text-[var(--text-primary)] mb-3">
            <Network className="h-3.5 w-3.5 text-[var(--text-muted)]" />
            Topology · <span className="font-mono">{topology.id}</span>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {topology.agents.map((agent, i) => (
              <React.Fragment key={agent}>
                <div className="rounded-[var(--radius)] border border-[var(--border-default)] bg-[var(--surface-base)] px-3 py-2 min-w-[9rem]">
                  <div className="text-xs font-bold text-[var(--text-primary)]">Agent {agent}</div>
                  <div className="text-[10px] text-[var(--text-muted)] font-mono mt-1">
                    tools: {topology.tool_auth[agent]?.join(', ') || 'none'}
                  </div>
                  <div className="text-[10px] text-[var(--text-muted)] font-mono">
                    state: {topology.state_auth[agent]?.join(', ') || 'none'}
                  </div>
                </div>
                {i < topology.agents.length - 1 && (
                  <ArrowRight className="h-4 w-4 text-[var(--text-muted)] shrink-0" />
                )}
              </React.Fragment>
            ))}
          </div>
        </section>
      )}

      {/* Launcher */}
      <section className="rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)] p-4 space-y-4">
        <div className="grid gap-4 md:grid-cols-4">
          <label className="block">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">Arm</span>
            <select
              value={arm}
              onChange={(e) => setArm(e.target.value)}
              disabled={running}
              className="mt-1 w-full rounded-[var(--radius)] border border-[var(--border-default)] bg-[var(--surface-base)] px-2 py-1.5 text-xs text-[var(--text-primary)]"
            >
              {arms.map((a) => (
                <option key={a.key} value={a.key}>{a.key}</option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">Repetitions</span>
            <input
              type="number"
              min={1}
              max={25}
              value={repetitions}
              onChange={(e) => setRepetitions(Math.max(1, Math.min(25, Number(e.target.value))))}
              disabled={running}
              className="mt-1 w-full rounded-[var(--radius)] border border-[var(--border-default)] bg-[var(--surface-base)] px-2 py-1.5 text-xs text-[var(--text-primary)]"
            />
          </label>

          <label className="block">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">Provider</span>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              disabled={running || scripted}
              className="mt-1 w-full rounded-[var(--radius)] border border-[var(--border-default)] bg-[var(--surface-base)] px-2 py-1.5 text-xs text-[var(--text-primary)] disabled:opacity-50"
            >
              <option value="ollama">ollama</option>
              <option value="nvidia">nvidia</option>
              <option value="groq">groq</option>
            </select>
          </label>

          <label className="block">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">Model</span>
            <input
              value={model}
              onChange={(e) => setModel(e.target.value)}
              disabled={running || scripted}
              placeholder="default"
              className="mt-1 w-full rounded-[var(--radius)] border border-[var(--border-default)] bg-[var(--surface-base)] px-2 py-1.5 text-xs font-mono text-[var(--text-primary)] disabled:opacity-50"
            />
          </label>
        </div>

        <label className="flex items-start gap-2 text-xs text-[var(--text-secondary)]">
          <input
            type="checkbox"
            checked={scripted}
            onChange={(e) => setScripted(e.target.checked)}
            disabled={running}
            className="mt-0.5"
          />
          <span>
            <span className="font-semibold text-[var(--text-primary)]">Scripted (no model calls)</span>
            {' — '}replays each case&apos;s compliant baseline script instead of calling an LLM.
            Exercises the whole pipeline deterministically and costs nothing.
          </span>
        </label>

        <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-[var(--border-subtle)]">
          <div className="text-xs text-[var(--text-secondary)]">
            <span className="font-mono font-semibold text-[var(--text-primary)]">{selectedCases.length}</span> cases ×{' '}
            <span className="font-mono font-semibold text-[var(--text-primary)]">{repetitions}</span> reps ={' '}
            <span className="font-mono font-semibold text-[var(--text-primary)]">{totalRuns}</span> runs
            <span className="text-[var(--text-muted)]"> (each repetition is a clean/attack pair)</span>
          </div>
          <div className="flex items-center gap-2">
            {running ? (
              <button
                onClick={stop}
                className="inline-flex items-center gap-1.5 rounded-[var(--radius)] border border-[var(--border-default)] bg-[var(--surface-base)] px-3 py-1.5 text-xs font-semibold text-[var(--text-primary)] hover:bg-[var(--surface-overlay)]"
              >
                <Square className="h-3.5 w-3.5" /> Stop
              </button>
            ) : (
              <button
                onClick={launch}
                disabled={selectedCases.length === 0}
                className="inline-flex items-center gap-1.5 rounded-[var(--radius)] bg-[var(--primary)] px-3 py-1.5 text-xs font-semibold text-[var(--primary-foreground)] hover:bg-[var(--primary-hover)] disabled:opacity-40"
              >
                <Play className="h-3.5 w-3.5" /> Launch experiment
              </button>
            )}
          </div>
        </div>

        {(running || progress.total > 0) && (
          <div className="space-y-1">
            <div className="flex items-center justify-between text-[10px] font-mono text-[var(--text-muted)]">
              <span>{progress.completed} / {progress.total} runs</span>
              {experimentId && (
                <Link href={`/lab/experiments/${experimentId}`} className="text-[var(--primary)] hover:underline">
                  view experiment →
                </Link>
              )}
            </div>
            <div className="h-1.5 w-full rounded-full bg-[var(--surface-base)] overflow-hidden">
              <div
                className="h-full bg-[var(--primary)] transition-all duration-300"
                style={{ width: progress.total ? `${(progress.completed / progress.total) * 100}%` : '0%' }}
              />
            </div>
          </div>
        )}
      </section>

      {/* Live runs */}
      {liveRuns.length > 0 && (
        <section className="rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)] overflow-hidden">
          <div className="px-4 py-2.5 border-b border-[var(--border-subtle)] text-xs font-semibold text-[var(--text-primary)]">
            Live runs
          </div>
          <div className="max-h-80 overflow-y-auto divide-y divide-[var(--border-subtle)]">
            {liveRuns.map((run) => (
              <div key={run.runId} className="flex items-center gap-3 px-4 py-2 text-xs">
                {run.done ? (
                  <CheckCircle2 className="h-3.5 w-3.5 text-[var(--success)] shrink-0" />
                ) : (
                  <Loader2 className="h-3.5 w-3.5 text-[var(--text-muted)] shrink-0 animate-spin" />
                )}
                <span className="font-mono font-semibold text-[var(--text-primary)]">{run.caseId}</span>
                <span className="font-mono text-[10px] text-[var(--text-muted)]">
                  {run.mode} · rep {run.repetition}
                </span>
                <span className="font-mono text-[10px] text-[var(--text-muted)]">{run.events} events</span>
                {run.verdict ? (
                  <span className={`ml-auto rounded border px-1.5 py-0.5 font-mono text-[10px] ${OBJECTIVE_STYLES[run.verdict.objective.level]}`}>
                    {run.verdict.objective.level}
                  </span>
                ) : (
                  <span className="ml-auto font-mono text-[10px] text-[var(--text-muted)]">
                    {run.done ? 'baseline' : ''}
                  </span>
                )}
                <Link
                  href={`/lab/runs/${run.runId}`}
                  className="text-[var(--primary)] hover:underline shrink-0 ml-auto"
                >
                  trace →
                </Link>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Case table */}
      <section className="rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)] overflow-hidden">
        <div className="px-4 py-2.5 border-b border-[var(--border-subtle)] flex items-center justify-between">
          <span className="text-xs font-semibold text-[var(--text-primary)]">
            Cases ({selectedCases.length}/{cases.length} selected)
          </span>
          <div className="flex items-center gap-3 text-[10px] font-mono text-[var(--text-muted)]">
            {Object.entries(selectedFamilies).map(([family, count]) => (
              <span key={family}>{FAMILY_LABELS[family] ?? family}: {count}</span>
            ))}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-[var(--surface-base)] text-[10px] uppercase tracking-wider text-[var(--text-muted)]">
              <tr>
                <th className="px-4 py-2 text-left font-semibold w-8"></th>
                <th className="px-2 py-2 text-left font-semibold">Case</th>
                <th className="px-2 py-2 text-left font-semibold">Family</th>
                <th className="px-2 py-2 text-left font-semibold">Entry</th>
                <th className="px-2 py-2 text-left font-semibold">Channel</th>
                <th className="px-2 py-2 text-left font-semibold">Eligible downstream</th>
                <th className="px-2 py-2 text-left font-semibold">Objective</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-subtle)]">
              {cases.map((c) => (
                <tr key={c.id} className="hover:bg-[var(--surface-base)]">
                  <td className="px-4 py-2">
                    <input
                      type="checkbox"
                      checked={selectedCases.includes(c.id)}
                      onChange={() => toggleCase(c.id)}
                      disabled={running}
                    />
                  </td>
                  <td className="px-2 py-2">
                    <div className="font-mono font-semibold text-[var(--text-primary)]">{c.id}</div>
                    <div className="text-[10px] text-[var(--text-muted)] max-w-md">{c.title}</div>
                  </td>
                  <td className="px-2 py-2 font-mono text-[10px] text-[var(--text-secondary)]">
                    {FAMILY_LABELS[c.family] ?? c.family}
                  </td>
                  <td className="px-2 py-2 font-mono text-[var(--text-secondary)]">{c.injection_point}</td>
                  <td className="px-2 py-2 font-mono text-[10px] text-[var(--text-secondary)]">{c.channel}</td>
                  <td className="px-2 py-2 font-mono text-[10px] text-[var(--text-secondary)]">
                    {c.eligible_downstream_agents.length
                      ? c.eligible_downstream_agents.join(', ')
                      : /* CPR is undefined here, not zero — §10.3 */
                        <span className="text-[var(--text-muted)] italic">none (entry-local)</span>}
                  </td>
                  <td className="px-2 py-2 text-[10px] text-[var(--text-secondary)] max-w-sm">{c.objective}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Past experiments */}
      <section className="rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)] overflow-hidden">
        <div className="px-4 py-2.5 border-b border-[var(--border-subtle)] text-xs font-semibold text-[var(--text-primary)]">
          Experiments
        </div>
        {experiments.length === 0 ? (
          <EmptyState
            title="No experiments yet"
            description="Launch one above. Scripted runs cost nothing and exercise the full pipeline."
          />
        ) : (
          <div className="divide-y divide-[var(--border-subtle)]">
            {experiments.map((e) => (
              <Link
                key={e.experiment_id}
                href={`/lab/experiments/${e.experiment_id}`}
                className="flex items-center gap-3 px-4 py-2.5 text-xs hover:bg-[var(--surface-base)]"
              >
                <span className="font-semibold text-[var(--text-primary)]">{e.name}</span>
                <span className="font-mono text-[10px] text-[var(--text-muted)]">{e.arm}</span>
                <span className="font-mono text-[10px] text-[var(--text-muted)]">
                  {new Date(e.created_at).toLocaleString()}
                </span>
                <ArrowRight className="h-3.5 w-3.5 text-[var(--text-muted)] ml-auto" />
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
