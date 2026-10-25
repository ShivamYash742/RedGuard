"use client"
import React, { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { AlertTriangle, ArrowRight, FlaskConical, Loader2, Play } from 'lucide-react'
import {
  labService, Arm, CaseSummary, Experiment, Topology, DEFAULT_MAX_STEPS, FAMILY_LABELS, armName, deriveRoute,
} from '@/lib/lab_mode/lab-service'
import { CHANNEL_ICONS, CHANNEL_NAMES, PropagationStage, RouteStrip } from '@/components/lab_mode/LabRoute'
import EmptyState from '@/components/shared/EmptyState'
import { TableSkeleton } from '@/components/shared/Skeletons'

/** Model calls per clean/attack pair, measured against nemotron-3-super in
 *  the P7 pilots. An estimate, labelled as one. */
const CALLS_PER_PAIR = 59

/** Local model the launcher offers first; `python -m core.lab_mode.smoke` is how
 *  a model is checked against the 10% parse-failure gate. */
const DEFAULT_LOCAL_MODEL = 'granite3.3:2b'
/** Scripted slow motion: slow enough to follow A → B → C in a demo. */
const DEMO_STEP_DELAY_MS = 700

const field = 'mt-1 w-full rounded-[var(--radius)] border border-[var(--border-default)] bg-[var(--surface-base)] px-2.5 py-2 text-sm text-[var(--text-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--primary)] disabled:opacity-50'
const label = 'text-xs font-semibold text-[var(--text-secondary)]'

export default function LabPage() {
  const router = useRouter()
  const [cases, setCases] = useState<CaseSummary[]>([])
  const [arms, setArms] = useState<Arm[]>([])
  const [topology, setTopology] = useState<Topology | null>(null)
  const [experiments, setExperiments] = useState<Experiment[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [selected, setSelected] = useState<string[]>([])
  const [arm, setArm] = useState('attack')
  const [repetitions, setRepetitions] = useState(5)
  const [maxSteps, setMaxSteps] = useState(DEFAULT_MAX_STEPS)
  const [scripted, setScripted] = useState(false)
  const [slowMotion, setSlowMotion] = useState(true)
  const [temperature, setTemperature] = useState(0)
  const [seed, setSeed] = useState('')
  const [provider, setProvider] = useState('ollama')
  const [model, setModel] = useState(DEFAULT_LOCAL_MODEL)
  const [launching, setLaunching] = useState(false)

  useEffect(() => {
    Promise.all([labService.fetchCases(), labService.fetchArms(), labService.fetchTopologies(), labService.fetchExperiments()])
      .then(([caseList, armList, topologies, experimentList]) => {
        setCases(caseList)
        setSelected(caseList.map((c) => c.id))
        setArms(armList)
        setTopology(topologies.topologies[0] ?? null)
        setExperiments(experimentList)
      })
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false))
  }, [])

  const pairs = selected.length * repetitions
  const toggle = (id: string) => setSelected((prev) => (prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]))
  const emptyRoute = useMemo(() => (topology ? deriveRoute([], topology.agents) : null), [topology])

  const launch = async (check = false) => {
    setError(null)
    setLaunching(true)
    try {
      // A model check is one case, one pair, no defence: enough steps for
      // the page's parse-failure gate to say whether the model can drive
      // the harness, in minutes rather than a sweep's hours.
      const created = await labService.createExperiment(check ? {
        name: `Model check · ${provider} / ${model || 'provider default'}`,
        arm: 'attack', cases: [cases[0]?.id ?? 'RGM-001'], repetitions: 1, max_steps: maxSteps,
        provider, model: model || undefined,
      } : {
        arm, cases: selected, repetitions, max_steps: maxSteps, scripted,
        step_delay_ms: scripted && slowMotion ? DEMO_STEP_DELAY_MS : undefined,
        provider, model: model || undefined,
        temperature, seed: seed.trim() === '' ? undefined : Math.trunc(Number(seed)),
      })
      router.push(`/lab/experiments/${created.experiment_id}?run=1`)
    } catch (err) {
      setError(String(err))
      setLaunching(false)
    }
  }

  if (loading) return <TableSkeleton />

  const renderList = (rows: Experiment[]) => (
    <ul className="divide-y divide-[var(--border-subtle)]">
      {rows.map((e) => {
        const config = e.config as { scripted?: boolean; model?: { model?: string }; cases?: string[]; repetitions?: number }
        return (
          <li key={e.experiment_id}>
            <Link href={`/lab/experiments/${e.experiment_id}`}
              className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-0.5 px-4 py-3 hover:bg-[var(--surface-base)] focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--primary)] sm:grid-cols-[minmax(0,1fr)_11rem_minmax(0,14rem)_10rem_1rem]">
              <span className="flex min-w-0 items-center gap-2">
                {e.live && (
                  <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-[color-mix(in_srgb,var(--primary)_12%,transparent)] px-2 py-0.5 text-xs font-semibold text-[var(--primary)]">
                    <span className="h-1.5 w-1.5 rounded-full bg-current motion-safe:animate-pulse" aria-hidden />
                    live · <span className="tabular-nums">{e.live.completed}/{e.live.total}</span>
                  </span>
                )}
                <span className="truncate text-sm font-semibold text-[var(--text-primary)]">{e.name}</span>
              </span>
              <span className="hidden text-sm text-[var(--text-secondary)] sm:block">{armName(e.arm)}</span>
              <span className="hidden truncate font-mono text-xs text-[var(--text-secondary)] sm:block">{config.scripted ? 'scripted' : config.model?.model ?? 'model'}</span>
              <span className="text-xs tabular-nums text-[var(--text-secondary)]">{new Date(e.created_at).toLocaleString()}</span>
              <ArrowRight className="hidden h-4 w-4 text-[var(--text-secondary)] sm:block" aria-hidden />
            </Link>
          </li>
        )
      })}
    </ul>
  )

  return (
    <div className="space-y-6">
      <header className="border-b border-[var(--border-subtle)] pb-5">
        <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)]">Multi-agent lab</h1>
        <p className="mt-1 max-w-3xl text-sm text-[var(--text-secondary)]">
          Plant an attack in something one agent reads, then watch what the chain of agents does with it: who was
          influenced, how far it travelled, and which control sealed it. The harness executes every action, so every
          step is observed rather than self-reported.
        </p>
      </header>

      {error && (
        <div role="alert" className="flex items-start gap-2 rounded-[var(--radius)] border border-[var(--danger)]/30 bg-[var(--danger-bg)] p-3 text-sm text-[var(--text-primary)]">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--danger)]" />
          <span className="break-words">{error}</span>
        </div>
      )}

      {topology && emptyRoute && (
        <section aria-label="System under test" className="rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)]">
          <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-[var(--border-subtle)] px-4 py-3">
            <h2 className="text-base font-semibold text-[var(--text-primary)]">System under test</h2>
            <span className="text-xs text-[var(--text-secondary)]">
              Topology <span className="font-mono">{topology.id}</span> · each agent may only message the next · tools as listed
            </span>
          </div>
          <div className="overflow-x-auto px-4 py-2">
            <PropagationStage path={topology.agents} entry={null} channel={null} eligible={topology.agents} route={emptyRoute} toolAuth={topology.tool_auth} />
          </div>
        </section>
      )}

      <section aria-label="New experiment" className="rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)]">
        <h2 className="border-b border-[var(--border-subtle)] px-4 py-3 text-base font-semibold text-[var(--text-primary)]">New experiment</h2>
        <div className="space-y-5 px-4 py-4">
          <fieldset>
            <legend className={label}>Defence under test</legend>
            <div className="mt-2 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {arms.map((a) => (
                <label key={a.key}
                  className={`flex cursor-pointer gap-3 rounded-[var(--radius)] border p-3 transition-colors has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-[var(--primary)] ${arm === a.key
                    ? 'border-[var(--primary)] bg-[color-mix(in_srgb,var(--primary)_8%,transparent)]'
                    : 'border-[var(--border-default)] hover:border-[var(--text-secondary)]'}`}>
                  <input type="radio" name="arm" value={a.key} checked={arm === a.key} onChange={() => setArm(a.key)} className="mt-1 accent-[var(--primary)]" />
                  <span className="min-w-0">
                    <span className="block text-sm font-semibold text-[var(--text-primary)]">{armName(a.key)}</span>
                    <span className="mt-0.5 block text-xs text-[var(--text-secondary)]">{a.description}</span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <label className="block">
              <span className={label}>Repetitions per case</span>
              <input type="number" min={1} max={25} value={repetitions} className={field}
                onChange={(e) => setRepetitions(Math.max(1, Math.min(25, Number(e.target.value) || 1)))} />
            </label>
            <label className="block">
              <span className={label}>Steps per agent</span>
              <input type="number" min={1} max={50} value={maxSteps} className={field}
                onChange={(e) => setMaxSteps(Math.max(1, Math.min(50, Number(e.target.value) || 1)))} />
            </label>
            <label className="block">
              <span className={label}>Provider</span>
              <select value={provider} onChange={(e) => {
                setProvider(e.target.value)
                setModel(e.target.value === 'ollama' ? DEFAULT_LOCAL_MODEL : '')
              }} disabled={scripted} className={field}>
                <option value="ollama">ollama (local)</option>
                <option value="nvidia">nvidia</option>
                <option value="groq">groq</option>
              </select>
            </label>
            <label className="block">
              <span className={label}>Model</span>
              <input value={model} onChange={(e) => setModel(e.target.value)} disabled={scripted} placeholder="provider default" className={`${field} font-mono`} />
            </label>
            <label className="block">
              <span className={label}>Temperature</span>
              <input type="number" min={0} max={2} step={0.1} value={temperature} disabled={scripted} className={field}
                onChange={(e) => setTemperature(Math.max(0, Math.min(2, Number(e.target.value) || 0)))} />
            </label>
            <label className="block">
              <span className={label}>Seed (repetition N uses seed + N)</span>
              <input type="number" step={1} value={seed} disabled={scripted} placeholder="none" className={`${field} font-mono`}
                onChange={(e) => setSeed(e.target.value)} />
            </label>
          </div>
          {!scripted && repetitions > 1 && temperature === 0 && seed.trim() === '' && (
            <p role="alert" className="rounded-[var(--radius)] border border-[var(--warning)] px-3 py-2 text-xs text-[var(--text-primary)]">
              {repetitions} repetitions at temperature 0 with no seed are likely exact copies of each other, so the number of cases, not
              the number of runs, is the sample size. Set a seed (it is varied per repetition) or a temperature above 0.
            </p>
          )}

          <div className="space-y-2">
            <label className="flex items-start gap-2.5 text-sm text-[var(--text-secondary)]">
              <input type="checkbox" checked={scripted} onChange={(e) => setScripted(e.target.checked)} className="mt-0.5 accent-[var(--primary)]" />
              <span>
                <span className="font-semibold text-[var(--text-primary)]">Instant demo (no model)</span>: each case&apos;s
                compliant script stands in for the model. It exercises the whole pipeline and costs nothing, and its
                attacks never land, so it tests the harness, not a model.
              </span>
            </label>
            {scripted && (
              <label className="ml-6 flex items-start gap-2.5 text-sm text-[var(--text-secondary)]">
                <input type="checkbox" checked={slowMotion} onChange={(e) => setSlowMotion(e.target.checked)} className="mt-0.5 accent-[var(--primary)]" />
                <span>
                  <span className="font-semibold text-[var(--text-primary)]">Slow motion</span>: pause {DEMO_STEP_DELAY_MS / 1000} s
                  per step so the run can be followed agent by agent.
                </span>
              </label>
            )}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border-subtle)] pt-4">
            <p className="text-sm text-[var(--text-secondary)]">
              <span className="font-mono font-semibold tabular-nums text-[var(--text-primary)]">{selected.length}</span> cases ×{' '}
              <span className="font-mono font-semibold tabular-nums text-[var(--text-primary)]">{repetitions}</span> repetitions ={' '}
              <span className="font-mono font-semibold tabular-nums text-[var(--text-primary)]">{pairs}</span> clean/attack pairs
              {!scripted && pairs > 0 && (
                <> · about <span className="font-mono font-semibold tabular-nums text-[var(--text-primary)]">{(pairs * CALLS_PER_PAIR).toLocaleString()}</span> model calls at the rate the pilots measured</>
              )}
            </p>
            <div className="flex flex-wrap gap-2">
              {!scripted && (
                <button onClick={() => launch(true)} disabled={launching} title="One case, one clean/attack pair: shows whether this model can emit valid actions before you spend a sweep on it"
                  className="inline-flex items-center gap-1.5 rounded-[var(--radius)] border border-[var(--border-default)] bg-[var(--surface-raised)] px-4 py-2 text-sm font-semibold text-[var(--text-primary)] hover:border-[var(--text-secondary)] disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]">
                  <FlaskConical className="h-4 w-4" /> Test model
                </button>
              )}
              <button onClick={() => launch()} disabled={selected.length === 0 || launching}
                className="inline-flex items-center gap-1.5 rounded-[var(--radius)] bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-[var(--primary-foreground)] hover:bg-[var(--primary-hover)] disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]">
                {launching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                Launch and watch
              </button>
            </div>
          </div>
        </div>
      </section>

      <section aria-label="Security test cases" className="overflow-hidden rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)]">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border-subtle)] px-4 py-3">
          <h2 className="text-base font-semibold text-[var(--text-primary)]">
            Security test cases <span className="font-normal text-[var(--text-secondary)]">· {selected.length} of {cases.length} selected</span>
          </h2>
          <div className="flex gap-3 text-sm font-semibold">
            <button onClick={() => setSelected(cases.map((c) => c.id))} className="text-[var(--primary)] hover:underline">All</button>
            <button onClick={() => setSelected([])} className="text-[var(--primary)] hover:underline">None</button>
          </div>
        </div>
        <ul className="divide-y divide-[var(--border-subtle)]">
          {cases.map((c) => {
            const Icon = CHANNEL_ICONS[c.channel]
  return (
              <li key={c.id}>
                <label className="grid cursor-pointer grid-cols-[1.25rem_1fr] gap-x-3 gap-y-2 px-4 py-3 hover:bg-[var(--surface-base)] lg:grid-cols-[1.25rem_minmax(0,1.3fr)_224px_minmax(0,1fr)] lg:items-center">
                  <input type="checkbox" checked={selected.includes(c.id)} onChange={() => toggle(c.id)} className="mt-1 accent-[var(--primary)] lg:mt-0" />
                  <span className="min-w-0">
                    <span className="font-mono text-sm font-bold text-[var(--text-primary)]">{c.id}</span>
                    <span className="ml-2 text-sm text-[var(--text-primary)]">{c.title}</span>
                    <span className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-xs text-[var(--text-secondary)]">
                      {FAMILY_LABELS[c.family] ?? c.family} ·{Icon && <Icon className="h-3.5 w-3.5" aria-hidden />}
                      enters via {CHANNEL_NAMES[c.channel] ?? c.channel} at {c.injection_point} ·{' '}
                      {c.eligible_downstream_agents.length ? `can reach ${c.eligible_downstream_agents.join(', ')}` : 'entry-local, nothing downstream to reach'}
                      {c.task_endorses_channel ? ' · the task points the agents at this channel' : ''}
                      {c.role === 'control' ? ' · control, reported apart' : ''}
                    </span>
                  </span>
                  <span className="col-start-2 lg:col-start-auto">
                    <RouteStrip path={c.expected_path} entry={c.injection_point} channel={c.channel} eligible={c.eligible_downstream_agents} />
                  </span>
                  <span className="col-start-2 text-xs text-[var(--text-secondary)] lg:col-start-auto">{c.objective}</span>
                </label>
              </li>
            )
          })}
        </ul>
      </section>

      <section aria-label="Experiments" className="overflow-hidden rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)]">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border-subtle)] px-4 py-3">
          <h2 className="text-base font-semibold text-[var(--text-primary)]">Experiments</h2>
          <Link href="/lab/compare" className="inline-flex items-center gap-1 text-sm font-semibold text-[var(--primary)] hover:underline">
            Compare defences <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
        {experiments.length === 0 ? (
          <EmptyState title="No experiments yet" description="Launch one above. The instant demo costs nothing and shows the whole pipeline working." />
        ) : (
          <>
            {renderList(experiments.filter((e) => e.vintage !== 'pre_audit'))}
            {experiments.some((e) => e.vintage === 'pre_audit') && (
              <div className="border-t border-[var(--border-default)]">
                <div className="px-4 py-3">
                  <h3 className="text-sm font-semibold text-[var(--text-primary)]">Measured before the audit fixes</h3>
                  <p className="mt-0.5 max-w-3xl text-xs text-[var(--text-secondary)]">
                    Judged with the 1.2.0 evaluator and metrics (substring predicates, controls and unreachable cases pooled,
                    unexposed runs counted as resisted). Not comparable with the experiments above and never pooled with them.
                  </p>
                </div>
                {renderList(experiments.filter((e) => e.vintage === 'pre_audit'))}
              </div>
            )}
          </>
        )}
      </section>
    </div>
  )
}
