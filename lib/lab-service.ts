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

/** Mirrors `core/lab/runner.DEFAULT_MAX_STEPS` — the budget E2 measured. */
export const DEFAULT_MAX_STEPS = 10

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
  /** How many clean runs defined "normal behaviour" for this verdict: 1 for
   *  its paired run alone, N once rescored against all of its case's clean
   *  repetitions. Provenance, not a fifth dimension. */
  baseline_runs?: number
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

/** A rate with its 95% interval. `value: null` means undefined, not zero.
 *
 *  Runs of one case succeed or fail together, so the interval is Wilson's
 *  over the effective sample size (`n_eff`) rather than over `n` runs as if
 *  they were independent. `ci_method` says which: plain `wilson` when there
 *  is only one case to cluster by. */
export interface RateWithCI {
  value: number | null
  n: number
  ci: [number, number] | null
  ci_method?: 'wilson' | 'wilson_design_effect' | null
  n_eff?: number | null
  icc?: number | null
  n_cases?: number
}

export interface ExperimentMetrics {
  experiment_id: string
  arm: string
  n_attack_runs: number
  /** Pairs left out of every rate: a run hit a harness error or never finished. */
  n_failed_pairs: number
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

/** One arm against another, case by case (`analysis._paired`): the unit this
 *  design generalises over is the case, not the run. `ci` is null below five
 *  shared cases, where a bootstrap has almost nothing to resample. */
export interface PairedDifference {
  n_cases: number
  mean_difference: number | null
  ci: [number, number] | null
  cases_lower: number
  cases_equal: number
  cases_higher: number
  excludes_zero: boolean | null
}

export interface RateComparison {
  baseline: RateWithCI
  variant: RateWithCI
  difference: number | null
  overlapping: boolean | null
  paired: PairedDifference
}

export interface ArmSummary {
  n_runs: number
  n_valid: number
  n_invalid: number
  icr: RateWithCI
  asr: RateWithCI
  partial_rate: RateWithCI
  cpr: number | 'n/a'
  cpr_denominator_size: number
  containment_rate: number | null
  mean_coverage: number | null
}

export interface ArmComparison {
  baseline_arm: string
  variant_arm: string
  metrics: {
    icr: RateComparison
    asr: RateComparison
    partial_rate: RateComparison
    cpr: { baseline: number | 'n/a'; variant: number | 'n/a'; comparable: boolean }
    containment_rate: { baseline: number | null; variant: number | null }
  }
  caveat: string
}

/** `GET /api/lab/compare` — §11's EXP-4/6/6b/6c/7/7b over pooled experiments. */
export interface CompareResult {
  arms: Record<string, ArmSummary>
  comparisons: Record<string, ArmComparison>
  warnings: string[]
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
  | { event: 'experiment_started'; data: { experiment_id: string; arm: string; cases: string[]; repetitions: number; total_runs: number; already_completed_pairs: number } }
  | { event: 'run_started'; data: { run_id: string; case_id: string; mode: string; pair_id: string; repetition_index: number } }
  | { event: 'trace_event'; data: LiveEvent & { run_id: string } }
  | { event: 'run_verdict'; data: { run_id: string; baseline_run_id: string; case_id: string; pair_id: string; repetition_index: number; status: string; verdict: Verdict; diagnostics: Record<string, unknown>; progress: { completed: number; total: number } } }
  | { event: 'case_rescored'; data: { case_id: string; baseline_runs: number; runs: { run_id: string; verdict: Verdict }[] } }
  | { event: 'experiment_complete'; data: { experiment_id: string; runs_completed: number } }
  | { event: 'experiment_error'; data: { experiment_id: string; error: string } }

const STREAM_EVENTS = [
  'experiment_started',
  'run_started',
  'trace_event',
  'run_verdict',
  'case_rescored',
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

  /** Rejects with the backend's reason when the experiments differ in more
   *  than their arm (model, step budget, scripted mode) or share one arm. */
  public async fetchCompare(experimentIds: string[]): Promise<CompareResult> {
    return getJSON(`/api/lab/compare?experiments=${experimentIds.map(encodeURIComponent).join(',')}`)
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
// Live tracking — one derivation shared by the live board and the replay
// ─────────────────────────────────────────────────────────────────────────────

/** Mirrors `evaluator._RESOURCE_ARG_KEYS`: the argument naming *which
 *  resource* an action touched. Free text stays out, as it does server-side.
 *  If the two disagree, the timeline shows a verdict with no visible
 *  supporting deviation, which reads as the tool contradicting itself. */
export const RESOURCE_ARG_KEYS = ['path', 'name', 'key', 'to'] as const

/** A trace event as the live stream carries it (`lab_api._event_payload`). */
export interface LiveEvent {
  step: number
  category: EventCategory
  event_type: string
  agent_id: string | null
  tool: string | null
  authorized: boolean | null
  derived_from: number[]
  content_tag: ContentTag | null
  /** What the action reached for: `{name: 'customer_pii'}`, `{to: 'B'}`, or
   *  for an injection event `{channel, location}`. */
  resource: Record<string, string | number> | null
  /** Why a refused action was refused (`not_authorized`, `capability_policy`, …). */
  reason: string | null
}

/** A stored event in the stream's shape, so a replay derives its state
 *  through exactly the function the live board uses. */
export function toLiveEvent(event: TraceEvent): LiveEvent {
  const args = (event.arguments && typeof event.arguments === 'object' ? event.arguments : {}) as Record<string, unknown>
  const meta = event.metadata ?? {}
  const injection = event.category === 'injection'
  const resource: Record<string, string | number> = {}
  for (const key of injection ? ['channel', 'location'] : RESOURCE_ARG_KEYS) {
    const value = injection ? args[key] || meta[key] : args[key]
    if (typeof value === 'number' || (typeof value === 'string' && (value !== '' || !injection))) resource[key] = value
  }
  return {
    step: event.step,
    category: event.category,
    event_type: event.event_type,
    agent_id: event.agent_id,
    tool: event.tool,
    authorized: event.authorized,
    derived_from: event.derived_from,
    content_tag: event.content_tag,
    resource: Object.keys(resource).length ? resource : null,
    reason: event.authorized === false && typeof meta.reason === 'string' ? meta.reason : null,
  }
}

export interface AgentTrack {
  /** Attack-derived content was in this agent's context. Observed, not a
   *  claim of influence — only the verdict decides that. */
  reached: boolean
  reachedAt: number | null
  active: boolean
  finished: boolean
  /** Its own actions the harness refused: a tool, a message or shared state. */
  refused: number
  lastAction: string | null
  lastStep: number | null
  lastRefused: boolean
}

export interface EdgeTrack {
  crossed: boolean
  /** An attack-derived message crossed this edge. */
  tainted: boolean
  taintedAt: number | null
  /** A message on this edge was refused: no edge, or the bus filter. */
  denied: boolean
  deniedAt: number | null
}

export interface RouteState {
  agents: Record<string, AgentTrack>
  edges: Record<string, EdgeTrack>
  planted: boolean
  finished: boolean
  count: number
  last: LiveEvent | null
}

export const edgeKey = (from: string, to: string) => `${from}>${to}`

const ARTIFACT_EVENTS = new Set(['artifact_planted', 'artifact_observed'])

/** Everything a route view shows, as of `upTo` (inclusive).
 *
 *  Attack derivation is the evaluator's own taint closure (`is_attack_derived`),
 *  computed incrementally: `derived_from` only ever points at earlier steps,
 *  so an event is derived exactly when it is an artifact event or one of its
 *  parents is. */
export function deriveRoute(events: LiveEvent[], agents: string[], upTo = Infinity): RouteState {
  const tainted = new Set<number>()
  const state: RouteState = { agents: {}, edges: {}, planted: false, finished: false, count: 0, last: null }
  for (const agent of agents) {
    state.agents[agent] = {
      reached: false, reachedAt: null, active: false, finished: false,
      refused: 0, lastAction: null, lastStep: null, lastRefused: false,
    }
  }

  for (const event of events) {
    if (event.step > upTo) break
    state.count += 1
    state.last = event

    const derived = ARTIFACT_EVENTS.has(event.event_type) || event.derived_from.some((p) => tainted.has(p))
    if (derived) tainted.add(event.step)
    if (event.event_type === 'artifact_planted') state.planted = true
    if (event.event_type === 'run_finished') {
      state.finished = true
      for (const agent of agents) state.agents[agent].active = false
    }

    const track = event.agent_id ? state.agents[event.agent_id] : undefined
    if (!track || !event.agent_id) continue
    if (derived && !track.reached) {
      track.reached = true
      track.reachedAt = event.step
    }
    if (event.event_type === 'agent_step_started') {
      for (const agent of agents) state.agents[agent].active = agent === event.agent_id
    }
    if (event.event_type === 'agent_finished') {
      track.finished = true
      track.active = false
    }

    const refused = event.authorized === false
    if (refused) track.refused += 1
    const action = actionLabel(event)
    if (action) {
      track.lastAction = action
      track.lastStep = event.step
      track.lastRefused = refused
    }

    const to = event.resource?.to
    if (typeof to === 'string' && (event.event_type === 'message_sent' || event.event_type === 'message_denied')) {
      const key = edgeKey(event.agent_id, to)
      const edge = state.edges[key] ?? (state.edges[key] = {
        crossed: false, tainted: false, taintedAt: null, denied: false, deniedAt: null,
      })
      if (event.event_type === 'message_denied') {
        edge.denied = true
        edge.deniedAt ??= event.step
      } else {
        edge.crossed = true
        if (derived && !edge.tainted) {
          edge.tainted = true
          edge.taintedAt = event.step
        }
      }
    }
  }
  return state
}

/** What an agent reached for, e.g. `db_query · customer_pii`. */
export function actionLabel(event: LiveEvent): string | null {
  const r = event.resource ?? {}
  const target = r.name ?? r.path ?? r.key
  switch (event.event_type) {
    case 'tool_requested':
    case 'tool_denied':
      return target !== undefined ? `${event.tool} · ${target}` : event.tool
    case 'message_sent':
    case 'message_denied':
      return `message → ${r.to}`
    case 'state_read':
      return `read ${r.key ?? 'state'}`
    case 'state_write':
      return `write ${r.key ?? 'state'}`
    case 'agent_report':
      return 'flagged content to operators'
    case 'action_parse_failed':
      return 'unparseable action'
    default:
      return null
  }
}

/** Plain-language gloss for each event type, so a trace is readable by
 *  someone who has not memorised §8's vocabulary. */
export const EVENT_LABELS: Record<string, string> = {
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
  agent_report: 'flagged content to operators',
  message_sent: 'sent message',
  message_delivered: 'message delivered',
  message_denied: 'message refused',
  message_received: 'received message',
  tool_requested: 'requested tool',
  tool_executed: 'tool executed',
  tool_denied: 'tool refused',
  tool_error: 'tool error',
  state_read: 'read shared state',
  state_write: 'wrote shared state',
}

export const REFUSAL_REASONS: Record<string, string> = {
  not_authorized: 'not in its permissions',
  capability_policy: 'capability policy',
  no_edge: 'no edge in the topology',
  content_filter: 'bus filter',
}

/** One line for a live ticker: who did what to which resource. */
export function describeEvent(event: LiveEvent): string {
  const who = event.agent_id ? `Agent ${event.agent_id}` : 'Harness'
  const r = event.resource ?? {}
  const action = actionLabel(event)
  switch (event.event_type) {
    case 'artifact_planted':
      return `Artifact planted in ${r.channel ?? 'the environment'}${r.location ? ` · ${r.location}` : ''}`
    case 'artifact_observed':
      return `${who} read the injected task`
    case 'tool_requested':
      return `${who} → ${action}`
    case 'tool_executed':
      return `${who} ← ${event.tool} returned`
    case 'tool_denied':
    case 'message_denied':
      return `${who} → ${action} · refused (${REFUSAL_REASONS[event.reason ?? ''] ?? event.reason ?? 'refused'})`
    case 'message_sent':
      return `${who} → Agent ${r.to}`
    case 'state_read':
    case 'state_write':
      return `${who} ${event.authorized === false ? `refused: ${action}` : action}`
    default:
      return `${who} · ${EVENT_LABELS[event.event_type] ?? event.event_type}`
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Vocabulary — the four verdict dimensions in words
// ─────────────────────────────────────────────────────────────────────────────

/** Short names for the execution arms; the API's `description` stays the
 *  source of truth for what each one does. */
export const ARM_NAMES: Record<string, string> = {
  attack: 'No defence',
  attack_validated: 'Prompt validation',
  attack_permissive_tools: 'Permissive tools',
  attack_bus_gateway: 'Bus filter (oracle)',
  attack_capability_gateway: 'Capability gateway',
}

export const armName = (key: string) => ARM_NAMES[key] ?? key

export const FAMILY_LABELS: Record<string, string> = {
  content_injection: 'Content injection',
  tool_manipulation: 'Tool manipulation',
  memory_poisoning: 'Memory poisoning',
  direct_injection: 'Direct injection',
}

/** Mirrors `runner.DEFAULT_ROLES`. */
export const AGENT_ROLES: Record<string, string> = {
  A: 'researcher',
  B: 'validator',
  C: 'executor',
}

export const IMPACT_LABELS: Record<AgentImpactLevel, string> = {
  COMPROMISED: 'compromised',
  INFLUENCED: 'influenced',
  NOT_INFLUENCED: 'not influenced',
}

export const OBJECTIVE_LABELS: Record<ObjectiveLevel, string> = {
  NOT_REACHED: 'not reached',
  PARTIALLY_REACHED: 'partially reached',
  REACHED: 'reached',
  CRITICAL_REACHED: 'critical',
}

export const MECHANISM_LABELS: Record<string, string> = {
  tool_denied: 'tool permission refused it',
  capability_denied: 'capability policy refused it',
  message_denied: 'bus refused the message',
  agent_non_compliance: 'agent did not comply',
  no_derived_content_delivered: 'attack content never arrived',
}

/** Mechanisms where the attack content reached the containing agent and
 *  stopped *there*; the others stopped it before it arrived. */
export const HELD_AT_AGENT = new Set(['agent_non_compliance', 'tool_denied', 'capability_denied'])

export const OUTCOME_LABELS: Record<SystemOutcome, string> = {
  TASK_COMPLETED_CLEANLY: 'task done',
  TASK_COMPLETED_WITH_DEVIATION: 'task done, deviated',
  TASK_FAILED: 'task failed',
  RUN_INVALID: 'invalid: baseline failed',
}

export function containmentLabel(verdict: Verdict): string {
  const c = verdict.containment
  if (c.status === 'CONTAINED') return `Sealed at ${c.agent}`
  if (c.status === 'NO_DOWNSTREAM_ELIGIBLE') return 'Entry-local'
  return 'Not contained'
}

export const CATEGORY_STYLES: Record<EventCategory, string> = {
  injection: 'text-[var(--danger)] border-[var(--danger)]/40',
  tool: 'text-[var(--primary)] border-[var(--primary)]/40',
  communication: 'text-[var(--accent)] border-[var(--accent)]/40',
  state: 'text-[var(--warning)] border-[var(--warning)]/40',
  agent: 'text-[var(--text-secondary)] border-[var(--border-default)]',
  system: 'text-[var(--text-secondary)] border-[var(--border-subtle)]',
  evaluation: 'text-[var(--text-secondary)] border-[var(--border-subtle)]',
}

/** `"n/a"` and `null` are meaningfully different from 0 and must not render
 *  as a number — §10.3's whole point. */
export function formatRate(value: number | null | 'n/a' | undefined, digits = 1): string {
  if (value === 'n/a') return 'n/a'
  if (value === null || value === undefined) return '—'
  return `${(value * 100).toFixed(digits)}%`
}
