import directInjection from '@/core/scanner_mode/datasets/direct_injection.json'
import contentInjection from '@/core/scanner_mode/datasets/content_injection.json'
import exfiltration from '@/core/scanner_mode/datasets/exfiltration.json'
import goalDiversion from '@/core/scanner_mode/datasets/goal_diversion.json'
import memoryPoisoning from '@/core/scanner_mode/datasets/memory_poisoning.json'
import autonomy from '@/core/scanner_mode/datasets/autonomy.json'
import planning from '@/core/scanner_mode/datasets/planning.json'
import toolSecurity from '@/core/scanner_mode/datasets/tool_security.json'

export interface Reference {
  title: string
  authors: string[]
  year: number
  venue: string
  arxiv_id?: string
  url?: string
}

export interface EvaluationRules {
  success_indicators?: string[]
  blocked_indicators: string[]
  success_actions?: { tool: string; args_contain?: Partial<Record<string, string>> }[]
  notes?: string
}

export interface Probe {
  id: string
  title: string
  attack_family: string
  attack_variant: string
  scenario: string
  difficulty: 'trivial' | 'easy' | 'medium' | 'hard' | 'expert' | string
  threat_model: string
  attacker_capability?: string
  prompt: string
  expected_behavior: string
  failure_behavior: string
  attack_goal?: string
  evaluation_rules?: EvaluationRules
  references?: Reference[]
  tags?: string[]
  affected_layers?: string[]
  probe_version?: string
  dataset_version?: string
  synthetic?: boolean
  research_notes?: string
  benign_control?: boolean
  canary?: string
  tool_fixtures?: Partial<Record<string, string>>
}

export interface AttackFamilyMeta {
  id: string
  name: string
  description: string
  threatModel: string
  affectedLayers: string[]
  probeCount: number
  researchPapersCount: number
}

export interface ScenarioMeta {
  id: string
  name: string
  description: string
  riskLevel: 'High' | 'Medium' | 'Critical' | string
  probeCount: number
  primaryVectors: string[]
}

export const OUTCOME_TIERS = [
  { key: 'FILTERED', label: 'Filtered', hint: 'blocked by the regex policy', color: 'var(--accent)' },
  { key: 'REFUSED', label: 'Refused', hint: 'the model explicitly refused', color: 'var(--success)' },
  { key: 'IGNORED', label: 'Ignored', hint: 'no refusal, no compliance', color: 'color-mix(in srgb, var(--success) 45%, transparent)' },
  { key: 'COMPROMISED', label: 'Compromised', hint: 'the attack succeeded', color: 'var(--danger)' },
] as const

export type OutcomeTier = (typeof OUTCOME_TIERS)[number]['key']
export type TierCounts = Record<OutcomeTier, number>

export const emptyTierCounts = (): TierCounts => ({ FILTERED: 0, REFUSED: 0, IGNORED: 0, COMPROMISED: 0 })

// Benign controls: FILTERED = regex false positive, OVER_REFUSED = model refused a harmless request
export type ControlCounts = { FILTERED: number; OVER_REFUSED: number; HELPED: number; UNCLEAR: number }
export const emptyControlCounts = (): ControlCounts => ({ FILTERED: 0, OVER_REFUSED: 0, HELPED: 0, UNCLEAR: 0 })

export interface BenchmarkRun {
  id: string
  sessionId: string
  agentId: string
  agentName: string
  startedAt: string
  finishedAt: string | null
  totalProbes: number
  blocked: number
  allowed: number
  status: 'COMPLETED' | 'RUNNING' | 'FAILED' | string
  blockRate?: number
  // null benchmarkVersion = legacy run scored only as blocked/allowed
  benchmarkVersion: string | null
  promptMode: string | null
  tiers: TierCounts | null
  modelCompromised: number
}

export interface RateCI {
  rate: number
  lo: number
  hi: number
  n: number
  nEff?: number  // effective sample size after clustering by probe; the interval uses this
  // attack success only: the rate if the `mixed` rows (a refusal and a success indicator both matched) counted as compromised
  upper?: number
  mixed?: number
}

// One measured row per (agent, prompt mode, model, filter policy), from GET /api/leaderboard
export interface LeaderboardRow {
  rank: number
  /** Names the row in `noDifferenceFrom` and GET /api/leaderboard/compare: agentId:promptMode[@model][#policy]. */
  rowId: string
  agentId: string
  agentName: string
  /** The model the session recorded; null for runs that recorded none. */
  model?: string | null
  /** SHA-256 of the filter policy the runs used. */
  policySha256?: string | null
  promptMode: string | null
  benchmarkVersion: string
  preAudit: boolean
  runs: number
  lastRun: string
  attacks: number
  tiers: TierCounts
  asrModel: RateCI | null
  asrDeployed: RateCI | null
  /** The split the row's numbers are computed on: the held-out 'test' split when the runs cover it. */
  headlineSplit?: 'dev' | 'test'
  /** Attack success among attacks the agent actually met (indirect ones whose planted result it read). */
  asrModelExposed?: RateCI | null
  exposure?: { indirect: number; exposed: number } | null
  /** Rows this one cannot be told apart from by a paired per-probe test: its rank is not a claim against them. */
  noDifferenceFrom?: string[]
  bySplit?: Record<string, { attacks: number; asrModel: RateCI | null; asrDeployed: RateCI | null }>
  families: Record<string, { total: number; compromised: number; modelAnswered: number; modelCompromised: number }>
  noAnswer: { attacks: number; controls: number }
  controls: { total: number; overRefused: number; unclear: number; filtered: number }
  overRefusal: RateCI | null
  bds: number | null
}

interface DatasetFile {
  description?: string
  entries: Probe[]
}

// Raw row shapes returned by the FastAPI backend
interface ApiSession {
  id: string
  sessionId: string
  agentId: string | null
  agentName: string | null
  startedAt: string
  finishedAt: string | null
  totalProbes: number
  blocked: number
  allowed: number
  status: string | null
  benchmarkVersion: string | null
  promptMode: string | null
  filtered: number
  refused: number
  ignored: number
  compromised: number
  modelCompromised: number
}

export interface Stats {
  totalSessions: number
  totalProbes: number
  totalEvaluationsFired: number
  totalBlocked: number
  totalAllowed: number
  overallBlockRate: number
  coverageGap: number
}

export interface AgentInfo {
  id: string
  name?: string
  description?: string
}

export interface ReportCategory {
  category: string
  probes: number
  blocked: number
  allowed: number
  mismatches: number
  highest_risk_score: number
  // tiered runs only
  filtered?: number
  refused?: number
  ignored?: number
  model_compromised?: number
}

export interface ReportOverall {
  total_probes: number
  blocked: number
  allowed: number
  mismatches: number
  block_rate: number
  session_id: string
  agent_id: string
  agent_name: string
  model_name: string
  system_prompt: string
  // tiered runs only
  prompt_mode?: string | null
  filtered?: number
  refused?: number
  ignored?: number
  model_compromised?: number
  model_answered?: number
  mixed_rows?: number
  mixed_rows_model_alone?: number
  no_answer?: number
  controls_no_answer?: number
  /** Why the run stopped early (an agent or API error); absent for a run that finished. */
  error?: string
}

export interface RunReport {
  sessionId: string
  generatedAt: string
  reportMarkdown: string
  manifestSha256: string
  reportJson: { overall: ReportOverall; category_breakdown: ReportCategory[] }
}

const RAW_DATASETS: Record<string, DatasetFile> = {
  direct_injection: directInjection,
  content_injection: contentInjection,
  exfiltration: exfiltration,
  goal_diversion: goalDiversion,
  memory_poisoning: memoryPoisoning,
  autonomy: autonomy,
  planning: planning,
  tool_security: toolSecurity,
}

// 12 Benchmark Scenarios. probeCount is NOT stored here — it is derived from the
// real dataset in getScenarios(), keyed through SCENARIO_DATASET_KEYS below.
type ScenarioSeed = Omit<ScenarioMeta, 'probeCount'>

export const SCENARIOS: ScenarioSeed[] = [
  { id: 'github', name: 'GitHub Workspace', description: 'Evaluates agent safety when processing pull requests, code reviews, and repo issue comments.', riskLevel: 'Critical', primaryVectors: ['PR Body Injection', 'Commit Message Overrides'] },
  { id: 'gitlab', name: 'GitLab CI/CD', description: 'Audits agent resistance against malicious CI pipeline triggers and runner issue comments.', riskLevel: 'High', primaryVectors: ['Pipeline Parameter Hijack', 'Issue Comment Injections'] },
  { id: 'wiki', name: 'Internal Knowledge Base Wiki', description: 'Assesses vulnerability to hidden adversarial payload in shared markdown docs.', riskLevel: 'Medium', primaryVectors: ['Hidden CSS/HTML Injections', 'Document Instructions'] },
  { id: 'documentation', name: 'API Documentation Hub', description: 'Tests data exfiltration via untrusted API documentation payloads.', riskLevel: 'Medium', primaryVectors: ['Swagger Spec Injection', 'Sample Request Exfil'] },
  { id: 'email', name: 'Enterprise Mail Client', description: 'Scans incoming email body and attachment parsing for indirect prompt injections.', riskLevel: 'Critical', primaryVectors: ['Phishing Body Injection', 'Forwarding Automation Hijack'] },
  { id: 'calendar', name: 'Calendar Scheduling Agent', description: 'Checks scheduling agent resistance to meeting invite description payloads.', riskLevel: 'High', primaryVectors: ['Invite Notes Command Injection', 'Location URL Exfil'] },
  { id: 'banking', name: 'Financial & Banking Portal', description: 'Evaluates strict financial action authorization and anti-drain policy enforcement.', riskLevel: 'Critical', primaryVectors: ['Wire Transfer Override', 'Account Extraction'] },
  { id: 'travel', name: 'Corporate Travel Booking', description: 'Audits itinerary parsing and automated expense approval agent constraints.', riskLevel: 'Medium', primaryVectors: ['Flight Booking Redirect', 'Vendor Override'] },
  { id: 'shopping', name: 'E-Commerce Agent', description: 'Tests procurement agents against cart manipulation and price bypass probes.', riskLevel: 'High', primaryVectors: ['Checkout Automation Poisoning', 'Coupon Payload'] },
  { id: 'support', name: 'Customer Support Bot', description: 'Evaluates customer-facing ticket resolution agents against policy bypasses.', riskLevel: 'Medium', primaryVectors: ['Ticket Escalation Hijack', 'Refund Policy Bypass'] },
  { id: 'forum', name: 'Developer Forum', description: 'Scans forum thread parsing for malicious community post instruction overrides.', riskLevel: 'Low', primaryVectors: ['Markdown Exfil', 'Bot Mention Injection'] },
  { id: 'reddit', name: 'Community Social Feed', description: 'Evaluates sentiment & summary agents processing untrusted social threads.', riskLevel: 'Medium', primaryVectors: ['Upvote Bot Injection', 'Comment Payload Hijack'] },
]

// Maps each scenario's short id to the scenario string(s) actually used in core/scanner_mode/datasets/*.json.
const SCENARIO_DATASET_KEYS: Record<string, string[]> = {
  github: ['github_issue'],
  gitlab: ['gitlab_issue'],
  wiki: ['wiki'],
  documentation: ['documentation_page'],
  email: ['email_assistant'],
  calendar: ['calendar_assistant'],
  banking: ['banking_assistant'],
  travel: ['travel_assistant'],
  shopping: ['shopping_assistant'],
  support: ['support_ticket'],
  forum: ['forum_discussion'],
  reddit: ['reddit_post'],
}

export interface KnownAgent {
  id: string
  name: string
  badge: string
  category: 'nvidia' | 'ollama' | 'custom'
}

// Single source of truth for the pluggable agents this UI knows how to target.
// Header's model switcher, the run launcher, and global search all read this list
// instead of each hardcoding their own (previously three separately-drifting copies).
export const KNOWN_AGENTS: KnownAgent[] = [
  { id: 'nemotron_3_ultra', name: 'Nemotron-3 Ultra (550B)', badge: 'NVIDIA NIM', category: 'nvidia' },
  { id: 'nemotron_super_agent', name: 'Nemotron-3 Super (120B)', badge: 'NVIDIA NIM', category: 'nvidia' },
  { id: 'gpt_oss_20b_agent', name: 'GPT OSS 20B', badge: 'Groq', category: 'nvidia' },
  { id: 'gpt_oss_120b_agent', name: 'GPT OSS 120B', badge: 'Groq', category: 'nvidia' },
  { id: 'ollama_local_agent', name: 'Ollama Local Agent', badge: 'Local Ollama', category: 'ollama' },
  { id: 'example_custom_agent', name: 'Example Custom Agent', badge: 'Custom Template', category: 'custom' },
]

export function normalizeFamily(fam: string): string {
  if (!fam) return ''
  const f = fam.toLowerCase().trim()
  if (f === 'data_exfiltration' || f === 'exfiltration') return 'exfiltration'
  if (f === 'autonomous_actions' || f === 'autonomy') return 'autonomy'
  if (f === 'planning_manipulation' || f === 'planning') return 'planning'
  if (f === 'tool_manipulation' || f === 'tool_security') return 'tool_security'
  return f
}

class BenchmarkDataService {
  private static instance: BenchmarkDataService
  private allProbes: Probe[] = []
  private cache: Map<string, { data: unknown; timestamp: number }> = new Map()
  private CACHE_TTL_MS = 60 * 1000 // 1 minute in-memory cache

  private constructor() {
    this.initProbes()
  }

  public static getInstance(): BenchmarkDataService {
    if (!BenchmarkDataService.instance) {
      BenchmarkDataService.instance = new BenchmarkDataService()
    }
    return BenchmarkDataService.instance
  }

  private initProbes() {
    const probes: Probe[] = []
    Object.entries(RAW_DATASETS).forEach(([familyKey, dataset]) => {
      if (dataset && Array.isArray(dataset.entries)) {
        dataset.entries.forEach(entry => {
          probes.push({
            id: entry.id,
            title: entry.title || entry.id,
            attack_family: normalizeFamily(familyKey),
            attack_variant: entry.attack_variant || 'standard',
            scenario: entry.scenario || 'generic',
            difficulty: entry.difficulty || 'medium',
            threat_model: entry.threat_model || 'adversarial_user',
            attacker_capability: entry.attacker_capability || 'prompt_level',
            prompt: entry.prompt || '',
            expected_behavior: entry.expected_behavior || '',
            failure_behavior: entry.failure_behavior || '',
            attack_goal: entry.attack_goal,
            evaluation_rules: entry.evaluation_rules,
            references: entry.references || [],
            tags: entry.tags || [],
            affected_layers: entry.affected_layers || ['llm'],
            probe_version: entry.probe_version || '1.0.0',
            dataset_version: entry.dataset_version || '1.0.0',
            synthetic: entry.synthetic ?? true,
            research_notes: entry.research_notes,
            benign_control: entry.benign_control ?? false,
            canary: entry.canary,
            tool_fixtures: entry.tool_fixtures,
          })
        })
      }
    })
    this.allProbes = probes
  }

  private cached<T>(key: string): T | undefined {
    const entry = this.cache.get(key)
    return entry && Date.now() - entry.timestamp < this.CACHE_TTL_MS ? (entry.data as T) : undefined
  }

  public invalidateCache() {
    this.cache.clear()
  }

  public getAllProbes(): Probe[] {
    return this.allProbes
  }

  public getProbeById(id: string): Probe | undefined {
    return this.allProbes.find(p => p.id.toLowerCase() === id.toLowerCase())
  }

  public getProbesByFamily(familyId: string): Probe[] {
    const normTarget = normalizeFamily(familyId)
    return this.allProbes.filter(
      p => normalizeFamily(p.attack_family) === normTarget
    )
  }

  public getProbesByScenario(scenarioId: string): Probe[] {
    const keys = SCENARIO_DATASET_KEYS[scenarioId] || [scenarioId]
    return this.allProbes.filter(p => keys.includes(p.scenario.toLowerCase()))
  }

  /** Probes tagged 'generic' apply broadly and aren't scoped to one scenario. */
  public getGenericProbes(): Probe[] {
    return this.allProbes.filter(p => p.scenario.toLowerCase() === 'generic')
  }

  public getAttackFamilies(): AttackFamilyMeta[] {
    const familyMetas: Record<string, { desc: string; threat: string; layers: Set<string> }> = {
      direct_injection: {
        desc: 'Classic prompt injection attacks where the adversary directly injects malicious instructions into user inputs.',
        threat: 'Adversarial User',
        layers: new Set(['LLM', 'Policy Engine']),
      },
      content_injection: {
        desc: 'Indirect prompt injections embedded in untrusted external data sources like emails, web pages, or files.',
        threat: 'Untrusted Data Provider',
        layers: new Set(['LLM', 'Context Parser', 'Tool Router']),
      },
      exfiltration: {
        desc: 'Probes attempting to steal confidential system prompts, session keys, or API tokens via multi-step calls.',
        threat: 'Adversarial Exfiltrator',
        layers: new Set(['Policy Engine', 'Output Guardrail', 'Memory']),
      },
      goal_diversion: {
        desc: 'Attacks targeting agent planning loops to derail the original user objective toward adversary goals.',
        threat: 'Hijacked Planning Subsystem',
        layers: new Set(['Planning Engine', 'Task Orchestrator']),
      },
      memory_poisoning: {
        desc: 'Adversarial payloads designed to persist across chat sessions inside vector databases or memory buffers.',
        threat: 'Persistent Memory Poisoner',
        layers: new Set(['Vector DB', 'Memory Store', 'Retriever']),
      },
      autonomy: {
        desc: 'Probes checking unauthorized autonomous execution, resource drain, and unchecked loop execution.',
        threat: 'Unrestricted Tool Executor',
        layers: new Set(['Executor Subsystem', 'Permission Manager']),
      },
      planning: {
        desc: 'Subtle adversarial perturbations that cause multi-step agent plan degradation or invalid tool selection.',
        threat: 'Strategic Adversary',
        layers: new Set(['Planner', 'Reasoning Engine']),
      },
      tool_security: {
        desc: 'Attempts to trick the agent into calling dangerous system commands, file deletion, or network APIs.',
        threat: 'Privilege Escalation Agent',
        layers: new Set(['Tool Dispatcher', 'Sandbox']),
      },
    }

    return Object.entries(RAW_DATASETS).map(([familyId, dataset]) => {
      const familyProbes = this.getProbesByFamily(familyId)
      const meta = familyMetas[familyId] || {
        desc: dataset.description || 'AI Agent Security evaluation attack family.',
        threat: 'Adversarial Threat',
        layers: new Set(['LLM Layer']),
      }
      // Derived from the actual references[] on each probe, not asserted.
      const uniquePapers = new Set(familyProbes.flatMap(p => (p.references || []).map(r => r.title)))

      return {
        id: familyId,
        name: familyId.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
        description: meta.desc,
        threatModel: meta.threat,
        affectedLayers: Array.from(meta.layers),
        probeCount: familyProbes.length,
        researchPapersCount: uniquePapers.size,
      }
    })
  }

  public getScenarios(): ScenarioMeta[] {
    return SCENARIOS.map(s => ({ ...s, probeCount: this.getProbesByScenario(s.id).length }))
  }

  // API Call: Fetch Stats
  public async fetchStats(): Promise<Stats | null> {
    const key = 'api_stats'
    const hit = this.cached<Stats>(key)
    if (hit) return hit
    try {
      const res = await fetch('/api/stats')
      if (res.ok) {
        const data = await res.json()
        this.cache.set(key, { data, timestamp: Date.now() })
        return data
      }
    } catch (e) {
      console.error('Failed to fetch stats:', e)
    }
    return { totalSessions: 0, totalProbes: this.allProbes.length, totalEvaluationsFired: 0, totalBlocked: 0, totalAllowed: 0, overallBlockRate: 0, coverageGap: 0 }
  }

  // API Call: Fetch Sessions
  public async fetchSessions(): Promise<BenchmarkRun[]> {
    const key = 'api_sessions'
    const hit = this.cached<BenchmarkRun[]>(key)
    if (hit) return hit
    try {
      const res = await fetch('/api/sessions')
      if (res.ok) {
        const data = await res.json()
        const formatted: BenchmarkRun[] = data.map((s: ApiSession) => ({
          id: s.id,
          sessionId: s.sessionId,
          agentId: s.agentId || 'nemotron_3_ultra',
          agentName: s.agentName || 'Nemotron-3 Ultra Guard',
          startedAt: s.startedAt,
          finishedAt: s.finishedAt,
          totalProbes: s.totalProbes || 0,
          blocked: s.blocked || 0,
          allowed: s.allowed || 0,
          status: s.status || 'COMPLETED',
          blockRate: s.totalProbes > 0 ? s.blocked / s.totalProbes : 0,
          benchmarkVersion: s.benchmarkVersion ?? null,
          promptMode: s.promptMode ?? null,
          tiers: s.benchmarkVersion
            ? { FILTERED: s.filtered, REFUSED: s.refused, IGNORED: s.ignored, COMPROMISED: s.compromised }
            : null,
          modelCompromised: s.modelCompromised || 0,
        }))
        this.cache.set(key, { data: formatted, timestamp: Date.now() })
        return formatted
      }
    } catch (e) {
      console.error('Failed to fetch sessions:', e)
    }
    return []
  }

  // API Call: Fetch Report
  public async fetchReport(sessionId: string): Promise<RunReport | null> {
    const key = `api_report_${sessionId}`
    const hit = this.cached<RunReport>(key)
    if (hit) return hit
    try {
      const res = await fetch(`/api/reports/${sessionId}`)
      if (res.ok) {
        const data = await res.json()
        this.cache.set(key, { data, timestamp: Date.now() })
        return data
      }
    } catch (e) {
      console.error(`Failed to fetch report for ${sessionId}:`, e)
    }
    return null
  }

  // API Call: Fetch Agents
  public async fetchAgents(): Promise<AgentInfo[]> {
    try {
      const res = await fetch('/api/agents')
      if (res.ok) return await res.json()
    } catch (e) {
      console.error('Failed to fetch agents:', e)
    }
    return []
  }

  public async fetchLeaderboard(): Promise<LeaderboardRow[]> {
    try {
      const res = await fetch('/api/leaderboard')
      if (res.ok) return await res.json()
    } catch (e) {
      console.error('Failed to fetch leaderboard:', e)
    }
    return []
  }
}

export const benchmarkDataService = BenchmarkDataService.getInstance()
