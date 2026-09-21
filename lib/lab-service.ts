/**
 * Mode B (multi-agent lab) API client.
 *
 * Same singleton shape as `data-service.ts`, but with no bundled JSON: Mode A
 * imports its probe corpus at build time because it is static, whereas every
 * Mode B answer comes from a run that already happened. Nothing here is
 * cached for that reason — a stale verdict is worse than a second request.
 *
 * Backend surface: MULTI_AGENT_LAB_PLAN.md §13, served by backend/lab_api.py
 * and proxied through next.config's /api/:path* rewrite.
 */

// ─────────────────────────────────────────────────────────────────────────────
// Verdict model (§9) — four orthogonal dimensions, never collapsed
// ─────────────────────────────────────────────────────────────────────────────

export type AgentImpactLevel = 'COMPROMISED' | 'INFLUENCED' | 'NOT_INFLUENCED'

export type ObjectiveLevel =
  | 'NOT_REACHED'
  | 'PARTIALLY_REACHED'
  | 'REACHED'
  | 'CRITICAL_REACHED'

export type SystemOutcome =
  | 'TASK_COMPLETED_CLEANLY'
  | 'TASK_COMPLETED_WITH_DEVIATION'
  | 'TASK_FAILED'
  | 'RUN_INVALID'

export interface AgentImpact {
  level: AgentImpactLevel
  evidence: number[]
}

export interface Verdict {
  agent_impact: Record<string, AgentImpact>
  objective: { level: ObjectiveLevel; evidence: number[] }
  containment: {
    status: 'CONTAINED' | 'NOT_CONTAINED' | 'NO_DOWNSTREAM_ELIGIBLE' | string
    agent: string | null
    mechanism: string | null
    evidence: number[]
    label: string
  }
  system_outcome: SystemOutcome
}

// ─────────────────────────────────────────────────────────────────────────────
// Trace (§8)
// ─────────────────────────────────────────────────────────────────────────────

export type EventCategory =
  | 'system'
  | 'agent'
  | 'communication'
  | 'tool'
  | 'state'
  | 'injection'
  | 'evaluation'

/** Observational label describing where content came from. NOT a trust level
 *  — §8 is explicit that no code path may branch on it as if it were one. */
export type ContentTag =
  | 'original_task'
  | 'external_content'
  | 'derived'
  | 'attacker_artifact'

export interface TraceEvent {
  step: number
  category: EventCategory
  event_type: string
  timestamp: string
  agent_id: string | null
  tool: string | null
  arguments: unknown
  result: unknown
  authorized: boolean | null
  source_event_id: number | null
  /** Immediate causal parents. Traceable influence, never a causal claim. */
  derived_from: number[]
  content_tag: ContentTag | null
  metadata: Record<string, unknown> | null
}

// ─────────────────────────────────────────────────────────────────────────────
// Cases, topologies, fixtures
// ─────────────────────────────────────────────────────────────────────────────

export interface CaseSummary {
  id: string
  title: string
  family: string
  injection_point: string
  channel: string
  severity: string
  topology_id: string
  cee_fixture: string
  objective: string
  eligible_downstream_agents: string[]
  expected_path: string[]
  case_version: string
}

export interface Topology {
  id: string
  version: string
  agents: string[]
  edges: [string, string][]
  tool_auth: Record<string, string[]>
  state_auth: Record<string, string[]>
}

export interface Arm {
  key: string
  description: string
  validation_mode: string
  permissive_tools: boolean
}

// ─────────────────────────────────────────────────────────────────────────────
// Experiments and runs
// ─────────────────────────────────────────────────────────────────────────────

export interface RunSummary {
  run_id: string
  case_id: string
  mode: 'CLEAN' | 'ATTACK'
  pair_id: string
  baseline_run_id: string | null
  repetition_index: number
  status: 'RUNNING' | 'COMPLETED' | 'FAILED' | 'INVALID' | string
  invalid_reason: string | null
  started_at: string
  finished_at: string | null
  verdict: Verdict | null
  metrics: Record<string, unknown> | null
}

/** The §17 stamp: what produced this experiment. `git_clean: false` means the
 *  result cannot be reconstructed from its commit; `null` means the question
 *  could not be answered, which is not the same as clean. */
export interface ReproStamp {
  versions: Record<string, string>
  git_commit: string | null
  git_clean: boolean | null
  python_version?: string
  platform?: string
  captured_at?: string
}

/** One CEE channel (files/web/db/kv) as key → contents. */
export type CeeSnapshot = Record<string, Record<string, unknown>>

export interface Experiment {
  experiment_id: string
  name: string
  arm: string
  config: Record<string, unknown>
  versions: ReproStamp
  created_at: string
  runs?: RunSummary[]
  run_count?: number
  status_counts?: Record<string, number>
}

export interface RunDetail extends RunSummary {
  experiment_id: string
  cee_before: CeeSnapshot | null
  cee_after: CeeSnapshot | null
  events: TraceEvent[]
  event_count: number
}

/** A rate with its Wilson interval. `value: null` means undefined, not zero. */
export interface RateWithCI {
  value: number | null
  n: number
  ci: [number, number] | null
}

export interface ExperimentMetrics {
  experiment_id: string
  arm: string
  n_attack_runs: number
  aggregate: {
    icr: RateWithCI
    asr: RateWithCI
    partial_rate: RateWithCI
    /** `"n/a"` when the denominator is empty — never 0.0 (§10.3). */
    cpr: number | 'n/a'
    cpr_denominator_size: number
    depth: number[]
    coverage: number[]
    mean_coverage: number | null
    containment_rate: number | null
    containment_histogram: { agent: string | null; mechanism: string | null; count: number }[]
  }
  per_case: Record<string, {
    n: number
    icr: number | null
    asr: number | null
    partial_rate: number | null
    cpr: number | 'n/a'
    soc: number | null
  }>
  trajectory_drift: Record<string, {
    attack: number | null
    null: number | null
    effect: number | null
    /** False until there are >= 2 clean repetitions to form a noise floor. */
    interpretable: boolean
    clean_repetitions: number
  }>
  run_counts: Record<string, number>
}

export interface CreateExperimentRequest {
  name?: string
  arm?: string
  cases?: string[]
  repetitions?: number
  provider?: string
  model?: string
  topology_id?: string
  max_steps?: number
  /** Replay each case's clean_script instead of calling a model. */
  scripted?: boolean
}

// ─────────────────────────────────────────────────────────────────────────────
// SSE payloads (§13)
// ─────────────────────────────────────────────────────────────────────────────

export type LabStreamEvent =
  | { event: 'experiment_started'; data: { experiment_id: string; arm: string; cases: string[]; repetitions: number; total_runs: number } }
  | { event: 'run_started'; data: { run_id: string; case_id: string; mode: string; pair_id: string; repetition_index: number } }
  | { event: 'trace_event'; data: { run_id: string; step: number; category: EventCategory; event_type: string; agent_id: string | null; tool: string | null; authorized: boolean | null; derived_from: number[]; content_tag: ContentTag | null } }
  | { event: 'run_verdict'; data: { run_id: string; baseline_run_id: string; case_id: string; pair_id: string; repetition_index: number; status: string; verdict: Verdict; diagnostics: Record<string, unknown>; progress: { completed: number; total: number } } }
  | { event: 'experiment_complete'; data: { experiment_id: string; runs_completed: number } }
  | { event: 'experiment_error'; data: { experiment_id: string; error: string } }

const STREAM_EVENTS = [
  'experiment_started',
  'run_started',
  'trace_event',
  'run_verdict',
  'experiment_complete',
  'experiment_error',
] as const

// ─────────────────────────────────────────────────────────────────────────────
// Service
// ─────────────────────────────────────────────────────────────────────────────

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) {
    // Surface the backend's own detail: it explains *why* (a clean run has no
    // evidence bundle, a case failed validation), which a bare status hides.
    let detail = res.statusText
    try {
      detail = (await res.json())?.detail ?? detail
    } catch {
      /* non-JSON error body — keep the status text */
    }
    throw new Error(`${path}: ${detail}`)
  }
  return res.json() as Promise<T>
}

class LabService {
  private static instance: LabService

  public static getInstance(): LabService {
    if (!LabService.instance) LabService.instance = new LabService()
    return LabService.instance
  }

  // ── catalog ──────────────────────────────────────────────────────────

  public async fetchCases(): Promise<CaseSummary[]> {
    const body = await getJSON<{ cases: CaseSummary[] }>('/api/lab/cases')
    return body.cases
  }

  public async fetchCase(caseId: string): Promise<Record<string, unknown>> {
    return getJSON(`/api/lab/cases/${caseId}`)
  }

  public async fetchTopologies(): Promise<{ topologies: Topology[]; tools: string[] }> {
    return getJSON('/api/lab/topologies')
  }

  public async fetchArms(): Promise<Arm[]> {
    const body = await getJSON<{ arms: Arm[] }>('/api/lab/arms')
    return body.arms
  }

  // ── experiments ──────────────────────────────────────────────────────

  public async createExperiment(request: CreateExperimentRequest): Promise<{ experiment_id: string; total_runs: number; cases: string[] }> {
    const res = await fetch('/api/lab/experiments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    })
    const body = await res.json()
    if (!res.ok) throw new Error(body?.detail ?? 'Failed to create experiment')
    return body
  }

  public async fetchExperiments(): Promise<Experiment[]> {
    const body = await getJSON<{ experiments: Experiment[] }>('/api/lab/experiments')
    return body.experiments
  }

  public async fetchExperiment(experimentId: string): Promise<Experiment> {
    return getJSON(`/api/lab/experiments/${experimentId}`)
  }

  public async fetchMetrics(experimentId: string): Promise<ExperimentMetrics> {
    return getJSON(`/api/lab/experiments/${experimentId}/metrics`)
  }

  // ── runs ─────────────────────────────────────────────────────────────

  public async fetchRun(runId: string): Promise<RunDetail> {
    return getJSON(`/api/lab/runs/${runId}`)
  }

  public async fetchEvidence(runId: string): Promise<Record<string, unknown>> {
    return getJSON(`/api/lab/runs/${runId}/evidence`)
  }

  /**
   * Stream an experiment's execution.
   *
   * Returns the `EventSource` so the caller can close it — this is the one
   * endpoint that calls a model, so an abandoned stream is a real cost.
   */
  public streamExperiment(
    experimentId: string,
    onEvent: (event: LabStreamEvent) => void,
    onError?: (error: Event) => void,
  ): EventSource {
    const source = new EventSource(`/api/lab/experiments/${experimentId}/run`)
    for (const name of STREAM_EVENTS) {
      source.addEventListener(name, (e) => {
        onEvent({ event: name, data: JSON.parse((e as MessageEvent).data) } as LabStreamEvent)
      })
    }
    source.onerror = (e) => onError?.(e)
    return source
  }
}

export const labService = LabService.getInstance()

// ─────────────────────────────────────────────────────────────────────────────
// Presentation helpers, kept beside the types they describe
// ─────────────────────────────────────────────────────────────────────────────

/** Verdict levels are ordinal; colour encodes severity, never safe/unsafe. */
export const IMPACT_STYLES: Record<AgentImpactLevel, string> = {
  COMPROMISED: 'text-[var(--danger)] bg-[var(--danger-bg)] border-[var(--danger)]/30',
  INFLUENCED: 'text-[var(--warning)] bg-[var(--warning-bg)] border-[var(--warning)]/30',
  NOT_INFLUENCED: 'text-[var(--text-muted)] bg-[var(--surface-base)] border-[var(--border-subtle)]',
}

export const OBJECTIVE_STYLES: Record<ObjectiveLevel, string> = {
  CRITICAL_REACHED: 'text-[var(--danger)] bg-[var(--danger-bg)] border-[var(--danger)]/30',
  REACHED: 'text-[var(--danger)] bg-[var(--danger-bg)] border-[var(--danger)]/30',
  PARTIALLY_REACHED: 'text-[var(--warning)] bg-[var(--warning-bg)] border-[var(--warning)]/30',
  NOT_REACHED: 'text-[var(--success)] bg-[var(--success-bg)] border-[var(--success)]/30',
}

export const CATEGORY_STYLES: Record<EventCategory, string> = {
  injection: 'text-[var(--danger)] border-[var(--danger)]/40',
  tool: 'text-[var(--primary)] border-[var(--primary)]/40',
  communication: 'text-[var(--accent)] border-[var(--accent)]/40',
  state: 'text-[var(--warning)] border-[var(--warning)]/40',
  agent: 'text-[var(--text-secondary)] border-[var(--border-default)]',
  system: 'text-[var(--text-muted)] border-[var(--border-subtle)]',
  evaluation: 'text-[var(--text-muted)] border-[var(--border-subtle)]',
}

/** `"n/a"` and `null` are meaningfully different from 0 and must not render
 *  as a number — §10.3's whole point. */
export function formatRate(value: number | null | 'n/a', digits = 1): string {
  if (value === 'n/a') return 'n/a'
  if (value === null || value === undefined) return '—'
  return `${(value * 100).toFixed(digits)}%`
}

export function formatCI(ci: [number, number] | null): string {
  if (!ci) return ''
  return `[${(ci[0] * 100).toFixed(0)}–${(ci[1] * 100).toFixed(0)}%]`
}
