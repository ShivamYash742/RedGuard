"use client"
import React from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { Database, FileText, Globe, KeyRound, MessageSquareText, type LucideIcon } from 'lucide-react'
import {
  AGENT_ROLES, AgentImpactLevel, HELD_AT_AGENT, IMPACT_LABELS, OBJECTIVE_LABELS, ObjectiveLevel,
  RouteState, Verdict, edgeKey,
} from '@/lib/lab-service'

/*
 * One visual grammar for every Mode B route view, so the ledger strip, the
 * live stage and the replay read the same way:
 *
 *   ○ not influenced   ◉ influenced   ● compromised   (shape carries the level:
 *   hazard and caution collapse under deuteranopia on the light theme)
 *   ━ attack content crossed an edge   ▮ sealed — where containment happened
 *   ◇ objective not reached  ◈ partially  ◆ reached
 *
 * Motion only ever reports an observed event: a tracer grows when derived
 * content crosses an edge, a ring pings once when an agent is first reached,
 * a seal drops where a refusal happened. Nothing moves between events.
 */

const EASE = [0.16, 1, 0.3, 1] as const

export const CHANNEL_ICONS: Record<string, LucideIcon> = {
  files: FileText,
  web: Globe,
  db: Database,
  kv: KeyRound,
  task: MessageSquareText,
}

export const CHANNEL_NAMES: Record<string, string> = {
  files: 'file',
  web: 'search result',
  db: 'database row',
  kv: 'shared memory',
  task: 'the task itself',
}

type NodeState = AgentImpactLevel | 'REACHED' | 'IDLE'

function Node({ cx, cy, r, state }: { cx: number; cy: number; r: number; state: NodeState }) {
  const stroke =
    state === 'COMPROMISED' || state === 'REACHED' ? 'var(--danger)'
      : state === 'INFLUENCED' ? 'var(--warning)'
        : 'var(--text-muted)'
  const heavy = state !== 'IDLE' && state !== 'NOT_INFLUENCED'
  return (
    <>
      <circle
        cx={cx} cy={cy} r={r} strokeWidth={heavy ? 2 : 1.5}
        style={{
          fill: state === 'COMPROMISED' ? 'var(--danger)' : 'transparent',
          stroke,
          transition: 'fill 200ms ease-out, stroke 200ms ease-out',
        }}
      />
      {state === 'INFLUENCED' && <circle cx={cx} cy={cy} r={r * 0.42} style={{ fill: 'var(--warning)' }} />}
    </>
  )
}

function diamond(cx: number, cy: number, h: number) {
  return `M${cx} ${cy - h}L${cx + h} ${cy}L${cx} ${cy + h}L${cx - h} ${cy}Z`
}

function Goal({ cx, cy, h, level }: { cx: number; cy: number; h: number; level: ObjectiveLevel | null }) {
  const hit = level === 'REACHED' || level === 'CRITICAL_REACHED'
  const stroke = hit ? 'var(--danger)' : level === 'PARTIALLY_REACHED' ? 'var(--warning)' : 'var(--text-muted)'
  return (
    <>
      <path
        d={diamond(cx, cy, h)} strokeWidth={level && level !== 'NOT_REACHED' ? 2 : 1.5} strokeLinejoin="round"
        style={{ fill: hit ? 'var(--danger)' : 'transparent', stroke, transition: 'fill 200ms ease-out, stroke 200ms ease-out' }}
      />
      {level === 'PARTIALLY_REACHED' && (
        <path d={`M${cx} ${cy - h}L${cx} ${cy + h}L${cx - h} ${cy}Z`} style={{ fill: 'var(--warning)' }} />
      )}
      {level === 'CRITICAL_REACHED' && (
        <path d={diamond(cx, cy, h + 3.5)} strokeWidth={1} style={{ fill: 'none', stroke: 'var(--danger)' }} />
      )}
    </>
  )
}

export function ImpactGlyph({ level, size = 12 }: { level: NodeState; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 12 12" aria-hidden className="shrink-0 inline-block">
      <Node cx={6} cy={6} r={4.6} state={level} />
    </svg>
  )
}

export function ObjectiveGlyph({ level, size = 12 }: { level: ObjectiveLevel | null; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 14 14" aria-hidden className="shrink-0 inline-block overflow-visible">
      <Goal cx={7} cy={7} h={level === 'CRITICAL_REACHED' ? 3.6 : 5.2} level={level} />
    </svg>
  )
}

export function SealGlyph({ size = 12 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 12 12" aria-hidden className="shrink-0 inline-block">
      <rect x={4.5} y={0.5} width={3} height={11} rx={1.5} style={{ fill: 'var(--success)' }} />
    </svg>
  )
}

export function TracerGlyph({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size * 0.6} viewBox="0 0 14 8" aria-hidden className="shrink-0 inline-block">
      <line x1={1} y1={4} x2={13} y2={4} strokeWidth={2} strokeLinecap="round" style={{ stroke: 'var(--danger)' }} />
    </svg>
  )
}

/** The legend every route view shares; it names every mark a strip can draw. */
export function RouteLegend({ className = '' }: { className?: string }) {
  const item = 'inline-flex items-center gap-1.5'
  return (
    <div className={`flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-[var(--text-secondary)] ${className}`}>
      <span className={item}><ImpactGlyph level="NOT_INFLUENCED" /> not influenced</span>
      <span className={item}><ImpactGlyph level="REACHED" /> reached, verdict pending</span>
      <span className={item}><ImpactGlyph level="INFLUENCED" /> influenced</span>
      <span className={item}><ImpactGlyph level="COMPROMISED" /> compromised</span>
      <span className={item}><TracerGlyph /> attack content crossed</span>
      <span className={item}><SealGlyph /> sealed</span>
      <span className={item}><ObjectiveGlyph level="NOT_REACHED" /><ObjectiveGlyph level="PARTIALLY_REACHED" /><ObjectiveGlyph level="REACHED" /> objective</span>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Geometry shared by the strip and the stage
// ─────────────────────────────────────────────────────────────────────────────

interface RouteProps {
  /** `eligibility.expected_path`, in execution order. */
  path: string[]
  /** `attack.injection_point`; null for a clean run or a bare topology. */
  entry: string | null
  channel: string | null
  eligible: string[]
  route?: RouteState | null
  verdict?: Verdict | null
  /** Animate changes as they happen. Off for anything loaded settled. */
  live?: boolean
}

function nodeState(agent: string, route?: RouteState | null, verdict?: Verdict | null): NodeState {
  if (verdict) return verdict.agent_impact[agent]?.level ?? 'NOT_INFLUENCED'
  if (route?.agents[agent]?.reached) return 'REACHED'
  return 'IDLE'
}

/** Which inter-agent edges carried attack content. From the trace when there
 *  is one; otherwise from the verdict's own claims — an INFLUENCED or
 *  COMPROMISED agent, or one that held the attack itself, was reached, and a
 *  linear chain reaches an agent only through the edges before it. A task
 *  channel reaches every agent directly, so it lights no edges. */
function taintedEdges(p: RouteProps): Set<number> {
  const lit = new Set<number>()
  if (p.route) {
    p.path.slice(0, -1).forEach((a, i) => {
      if (p.route?.edges[edgeKey(a, p.path[i + 1])]?.tainted) lit.add(i)
    })
    return lit
  }
  if (!p.verdict || !p.entry || p.channel === 'task') return lit
  const c = p.verdict.containment
  const heldAt = c.status === 'CONTAINED' && HELD_AT_AGENT.has(c.mechanism ?? '') ? c.agent : null
  const start = p.path.indexOf(p.entry)
  let furthest = -1
  p.path.forEach((a, i) => {
    const level = p.verdict?.agent_impact[a]?.level ?? 'NOT_INFLUENCED'
    if (i > start && (level !== 'NOT_INFLUENCED' || a === heldAt)) furthest = i
  })
  for (let i = start; i < furthest; i++) lit.add(i)
  return lit
}

/** Where the seal sits: just past the agent that held the attack, or just
 *  before the agent it never reached. */
function sealX(verdict: Verdict | null | undefined, path: string[], xs: number[], goalX: number): number | null {
  const c = verdict?.containment
  if (!c || c.status !== 'CONTAINED' || !c.agent) return null
  const i = path.indexOf(c.agent)
  if (i < 0) return null
  if (HELD_AT_AGENT.has(c.mechanism ?? '')) {
    const next = i + 1 < xs.length ? xs[i + 1] : goalX
    return xs[i] + (next - xs[i]) * 0.32
  }
  return i > 0 ? xs[i - 1] + (xs[i] - xs[i - 1]) * 0.68 : xs[i] - 16
}

function inletAgents(p: RouteProps): string[] {
  if (!p.entry) return []
  return p.channel === 'task' ? p.path : [p.entry]
}

// ─────────────────────────────────────────────────────────────────────────────
// Ledger strip — one attack run, 224 × 30
// ─────────────────────────────────────────────────────────────────────────────

const S = { x0: 18, gap: 68, y: 19, r: 6.5 }
const stripXs = (path: string[]) => path.map((_, i) => S.x0 + i * S.gap)
const stripGoal = (xs: number[]) => xs[xs.length - 1] + S.gap * 0.85

export function RouteStrip(props: RouteProps & { className?: string }) {
  const { path, entry, eligible, route, verdict, live = false } = props
  const reduced = useReducedMotion()
  const animate = live && !reduced
  const xs = stripXs(path)
  const goalX = stripGoal(xs)
  const lit = taintedEdges(props)
  const seal = sealX(verdict, path, xs, goalX)
  const hot = !!route?.planted || !!verdict
  const reach = new Set([entry, ...eligible])
  const objective = verdict?.objective.level ?? null
  const width = goalX + 12

  return (
    <svg width={width} height={30} viewBox={`0 0 ${width} 30`} className={`shrink-0 overflow-visible ${props.className ?? ''}`} role="img"
      aria-label={stripSummary(path, verdict, route)}>
      {inletAgents(props).map((agent) => {
        const x = xs[path.indexOf(agent)]
        return (
          <g key={`in-${agent}`} style={{ stroke: hot ? 'var(--danger)' : 'var(--text-muted)', fill: hot ? 'var(--danger)' : 'var(--text-muted)', transition: 'stroke 200ms, fill 200ms' }}>
            <line x1={x} y1={1} x2={x} y2={S.y - S.r - 4} strokeWidth={1.5} />
            <path d={`M${x - 2.5} ${S.y - S.r - 5}L${x + 2.5} ${S.y - S.r - 5}L${x} ${S.y - S.r - 2}Z`} stroke="none" />
          </g>
        )
      })}

      {path.slice(0, -1).map((a, i) => {
        const x1 = xs[i] + S.r + 3
        const x2 = xs[i + 1] - S.r - 3
        return (
          <g key={`e-${a}`}>
            <line x1={x1} y1={S.y} x2={x2} y2={S.y} strokeWidth={1} style={{ stroke: 'var(--border-default)' }} />
            {lit.has(i) && (
              <motion.path
                d={`M${x1} ${S.y}L${x2} ${S.y}`} strokeWidth={2} strokeLinecap="round" fill="none"
                style={{ stroke: 'var(--danger)' }}
                initial={animate ? { pathLength: 0 } : false} animate={{ pathLength: 1 }}
                transition={{ duration: 0.45, ease: EASE }}
              />
            )}
          </g>
        )
      })}

      <line x1={xs[xs.length - 1] + S.r + 3} y1={S.y} x2={goalX - 8} y2={S.y} strokeWidth={objective === 'REACHED' || objective === 'CRITICAL_REACHED' ? 2 : 1}
        style={{ stroke: objective === 'REACHED' || objective === 'CRITICAL_REACHED' ? 'var(--danger)' : 'var(--border-default)', transition: 'stroke 200ms' }} />

      {path.map((agent, i) => {
        const state = nodeState(agent, route, verdict)
        const track = route?.agents[agent]
        return (
          <g key={agent} opacity={reach.has(agent) ? 1 : 0.35}>
            <title>{`Agent ${agent} · ${state === 'REACHED' ? 'reached by attack content' : state === 'IDLE' ? 'not reached' : IMPACT_LABELS[state]}`}</title>
            {track?.active && !verdict && (
              <motion.circle cx={xs[i]} cy={S.y} r={S.r + 3.5} strokeWidth={1.5} fill="none" style={{ stroke: 'var(--primary)' }}
                animate={reduced ? { opacity: 0.85 } : { opacity: [0.25, 1, 0.25] }}
                transition={reduced ? undefined : { duration: 1.6, repeat: Infinity, ease: 'easeInOut' }} />
            )}
            {animate && track?.reachedAt != null && (
              <motion.circle key={`ping-${track.reachedAt}`} cx={xs[i]} cy={S.y} fill="none" strokeWidth={1.5} style={{ stroke: 'var(--danger)' }}
                initial={{ r: S.r, opacity: 0.8 }} animate={{ r: S.r + 9, opacity: 0 }} transition={{ duration: 0.8, ease: EASE }} />
            )}
            <Node cx={xs[i]} cy={S.y} r={S.r} state={state} />
          </g>
        )
      })}

      {seal !== null && (
        <motion.rect x={seal - 1.5} y={S.y - 8} width={3} height={16} rx={1.5} style={{ fill: 'var(--success)', originY: 0.5 }}
          initial={animate ? { scaleY: 0 } : false} animate={{ scaleY: 1 }} transition={{ duration: 0.25, ease: EASE }} />
      )}

      <Goal cx={goalX} cy={S.y} h={objective === 'CRITICAL_REACHED' ? 4.2 : 5.6} level={objective} />
    </svg>
  )
}

function stripSummary(path: string[], verdict?: Verdict | null, route?: RouteState | null): string {
  if (verdict) {
    const impact = path.map((a) => `${a} ${IMPACT_LABELS[verdict.agent_impact[a]?.level ?? 'NOT_INFLUENCED']}`).join(', ')
    return `${impact}; ${verdict.containment.label}; objective ${OBJECTIVE_LABELS[verdict.objective.level]}`
  }
  const reached = path.filter((a) => route?.agents[a]?.reached)
  return reached.length ? `Attack content reached ${reached.join(', ')}` : 'Not reached yet'
}

/** Column heads aligned to the strip's geometry. */
export function RouteAxis({ path }: { path: string[] }) {
  const xs = stripXs(path)
  const goalX = stripGoal(xs)
  const width = goalX + 12
  return (
    <svg width={width} height={14} viewBox={`0 0 ${width} 14`} aria-hidden className="shrink-0 overflow-visible">
      {path.map((agent, i) => (
        <text key={agent} x={xs[i]} y={10} textAnchor="middle" className="text-[10px] font-semibold" style={{ fill: 'var(--text-secondary)' }}>{agent}</text>
      ))}
      <text x={goalX} y={10} textAnchor="middle" className="text-[10px] font-semibold" style={{ fill: 'var(--text-secondary)' }}>goal</text>
    </svg>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Stage — the live view and the replay, 720 × 214
// ─────────────────────────────────────────────────────────────────────────────

const W = 720
const G = { cy: 110, r: 20, top: 14, boxH: 30 }

function clip(text: string, max: number) {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text
}

export function PropagationStage(props: RouteProps & {
  toolAuth?: Record<string, string[]>
  location?: string | null
  /** Show the verdict's final shapes, seal and objective. The replay passes
   *  it only once the cursor reaches the end: mid-trace, the stage shows
   *  what had been observed by then, not what the whole run was judged. */
  showVerdict?: boolean
}) {
  const { path, entry, channel, eligible, route, verdict, toolAuth, location, live = false, showVerdict = true } = props
  const reduced = useReducedMotion()
  const animate = live && !reduced
  const gap = path.length > 1 ? (W - 260) / (path.length - 1) : 0
  const xs = path.map((_, i) => 90 + i * gap)
  const goalX = W - 70
  const shownVerdict = showVerdict ? verdict : null
  const lit = taintedEdges({ ...props, verdict: shownVerdict })
  const seal = sealX(shownVerdict, path, xs, goalX)
  const reach = new Set([entry ?? path[0], ...eligible])
  const hot = !!route?.planted || !!shownVerdict
  const objective = shownVerdict?.objective.level ?? null
  const last = route?.last ?? null

  // A message crossing right now: the packet the eye should follow.
  const packet = last && last.event_type === 'message_sent' && typeof last.resource?.to === 'string' && last.agent_id
    ? { from: path.indexOf(last.agent_id), to: path.indexOf(last.resource.to as string), step: last.step,
        tainted: route?.edges[edgeKey(last.agent_id, last.resource.to as string)]?.taintedAt === last.step }
    : null

  const sourceLabel = channel
    ? channel === 'task' ? 'task · the instruction rides in the shared task' : `${channel} · ${location ?? CHANNEL_NAMES[channel] ?? ''}`
    : null
  const inlets = inletAgents(props)
  const SourceIcon = channel ? CHANNEL_ICONS[channel] : null
  let box: { x: number; w: number } | null = null
  if (sourceLabel && inlets.length) {
    const w = Math.min(W - 16, 42 + sourceLabel.length * 6.8)
    const centre = channel === 'task' ? (xs[0] + xs[xs.length - 1]) / 2 : xs[path.indexOf(inlets[0])]
    box = { x: Math.max(8, Math.min(W - w - 8, centre - w / 2)), w }
  }

  return (
    <svg viewBox={`0 0 ${W} 214`} className="block w-full min-w-[560px] max-w-[760px] mx-auto" role="img"
      aria-label={stripSummary(path, shownVerdict, route)}>
      {box && sourceLabel && (
        <g style={{ transition: 'opacity 200ms' }} opacity={hot ? 1 : 0.6}>
          <rect x={box.x} y={G.top} width={box.w} height={G.boxH} rx={5} strokeWidth={1}
            style={{ fill: 'var(--danger-bg)', stroke: hot ? 'var(--danger)' : 'var(--border-default)' }} />
          {SourceIcon && <SourceIcon x={box.x + 10} y={G.top + 8} width={14} height={14} style={{ color: 'var(--danger)' }} />}
          <text x={box.x + 30} y={G.top + 19.5} className="font-mono text-[11px]" style={{ fill: 'var(--text-primary)' }}>{sourceLabel}</text>
          {inlets.map((agent) => {
            const x = xs[path.indexOf(agent)]
            const y2 = G.cy - G.r - 7
            return (
              <g key={agent} style={{ stroke: hot ? 'var(--danger)' : 'var(--text-muted)', fill: hot ? 'var(--danger)' : 'var(--text-muted)' }}>
                <line x1={x} y1={G.top + G.boxH} x2={x} y2={y2} strokeWidth={1.5} />
                <path d={`M${x - 4} ${y2}L${x + 4} ${y2}L${x} ${y2 + 5}Z`} stroke="none" />
              </g>
            )
          })}
        </g>
      )}

      {path.slice(0, -1).map((a, i) => {
        const x1 = xs[i] + G.r + 6
        const x2 = xs[i + 1] - G.r - 6
        const denied = route?.edges[edgeKey(a, path[i + 1])]?.denied && !shownVerdict
        return (
          <g key={`e-${a}`}>
            <line x1={x1} y1={G.cy} x2={x2} y2={G.cy} strokeWidth={1} style={{ stroke: 'var(--border-default)' }} />
            <path d={`M${x2 - 7} ${G.cy - 4}L${x2} ${G.cy}L${x2 - 7} ${G.cy + 4}`} fill="none" strokeWidth={1} style={{ stroke: 'var(--border-default)' }} />
            {lit.has(i) && (
              <motion.path d={`M${x1} ${G.cy}L${x2} ${G.cy}`} strokeWidth={3} strokeLinecap="round" fill="none" style={{ stroke: 'var(--danger)' }}
                initial={animate ? { pathLength: 0 } : false} animate={{ pathLength: 1 }} transition={{ duration: 0.6, ease: EASE }} />
            )}
            {denied && (
              <motion.rect x={x2 - 22} y={G.cy - 13} width={4} height={26} rx={2} style={{ fill: 'var(--success)', originY: 0.5 }}
                initial={animate ? { scaleY: 0 } : false} animate={{ scaleY: 1 }} transition={{ duration: 0.25, ease: EASE }} />
            )}
          </g>
        )
      })}

      {packet && packet.from >= 0 && packet.to >= 0 && (
        <motion.circle key={`pkt-${packet.step}`} cy={G.cy} r={5} style={{ fill: packet.tainted ? 'var(--danger)' : 'var(--text-secondary)' }}
          initial={animate ? { cx: xs[packet.from] + G.r + 6, opacity: 1 } : false}
          animate={{ cx: xs[packet.to] - G.r - 6, opacity: [1, 1, 0] }}
          transition={{ duration: 0.7, ease: EASE, times: [0, 0.8, 1] }} />
      )}

      <line x1={xs[xs.length - 1] + G.r + 6} y1={G.cy} x2={goalX - 16} y2={G.cy}
        strokeWidth={objective === 'REACHED' || objective === 'CRITICAL_REACHED' ? 3 : 1}
        style={{ stroke: objective === 'REACHED' || objective === 'CRITICAL_REACHED' ? 'var(--danger)' : 'var(--border-default)', transition: 'stroke 200ms' }} />

      {path.map((agent, i) => {
        const state = nodeState(agent, route, shownVerdict)
        const track = route?.agents[agent]
        // Clipped after the prefix, and short enough that a caption centred
        // on the first agent never runs off the viewBox.
        const caption = track?.lastAction
          ? clip(track.lastRefused ? `refused: ${track.lastAction}` : track.lastAction, 24)
          : track?.active ? 'deciding…' : null
        return (
          <g key={agent} opacity={reach.has(agent) ? 1 : 0.4}>
            <title>{`Agent ${agent} (${AGENT_ROLES[agent] ?? 'agent'}) · ${state === 'REACHED' ? 'reached by attack content' : state === 'IDLE' ? 'not reached' : IMPACT_LABELS[state]}${track?.lastAction ? ` · last: ${track.lastAction}` : ''}`}</title>
            {track?.active && (
              <motion.circle cx={xs[i]} cy={G.cy} r={G.r + 8} strokeWidth={2} fill="none" style={{ stroke: 'var(--primary)' }}
                animate={reduced ? { opacity: 0.85 } : { opacity: [0.2, 0.95, 0.2] }}
                transition={reduced ? undefined : { duration: 1.6, repeat: Infinity, ease: 'easeInOut' }} />
            )}
            {animate && track?.reachedAt != null && (
              <motion.circle key={`ping-${track.reachedAt}`} cx={xs[i]} cy={G.cy} fill="none" strokeWidth={2} style={{ stroke: 'var(--danger)' }}
                initial={{ r: G.r, opacity: 0.8 }} animate={{ r: G.r + 22, opacity: 0 }} transition={{ duration: 0.9, ease: EASE }} />
            )}
            <Node cx={xs[i]} cy={G.cy} r={G.r} state={state} />
            <text x={xs[i]} y={G.cy + G.r + 22} textAnchor="middle" className="text-[13px]" style={{ fill: 'var(--text-primary)' }}>
              <tspan fontWeight={700}>{agent}</tspan>
              <tspan style={{ fill: 'var(--text-secondary)' }}>{` · ${AGENT_ROLES[agent] ?? 'agent'}`}</tspan>
            </text>
            {toolAuth && (
              <text x={xs[i]} y={G.cy + G.r + 39} textAnchor="middle" className="font-mono text-[10.5px]" style={{ fill: 'var(--text-secondary)' }}>
                {(toolAuth[agent] ?? []).join(' · ') || 'no tools'}
              </text>
            )}
            {caption && (
              // Opacity only: on an SVG element framer-motion reads `y` as a
              // transform, which would add to the attribute and push the
              // caption out of the viewBox.
              <motion.text key={`cap-${track?.lastStep ?? 'think'}`} x={xs[i]} y={G.cy + G.r + (toolAuth ? 58 : 42)} textAnchor="middle"
                className="font-mono text-[11px]" style={{ fill: track?.lastRefused ? 'var(--success)' : 'var(--text-primary)' }}
                initial={animate ? { opacity: 0 } : false} animate={{ opacity: 1 }} transition={{ duration: 0.2, ease: EASE }}>
                {caption}
              </motion.text>
            )}
          </g>
        )
      })}

      {seal !== null && (
        <motion.rect x={seal - 2} y={G.cy - 15} width={4} height={30} rx={2} style={{ fill: 'var(--success)', originY: 0.5 }}
          initial={animate ? { scaleY: 0 } : false} animate={{ scaleY: 1 }} transition={{ duration: 0.25, ease: EASE }} />
      )}

      <g>
        <title>{`Attacker objective · ${objective ? OBJECTIVE_LABELS[objective] : 'no verdict yet'}`}</title>
        <Goal cx={goalX} cy={G.cy} h={objective === 'CRITICAL_REACHED' ? 9 : 12} level={objective} />
      </g>
      <text x={goalX} y={G.cy + G.r + 22} textAnchor="middle" className="text-[13px]" style={{ fill: 'var(--text-secondary)' }}>objective</text>
      {objective && (
        <text x={goalX} y={G.cy + G.r + 39} textAnchor="middle" className="text-[11px] font-semibold" style={{ fill: 'var(--text-primary)' }}>
          {OBJECTIVE_LABELS[objective]}
        </text>
      )}
    </svg>
  )
}
