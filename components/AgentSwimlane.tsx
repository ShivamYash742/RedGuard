"use client"
import React, { useMemo } from 'react'
import { LiveEvent, describeEvent, formatDuration } from '@/lib/lab-service'

interface Bar { start: number; end: number; open: boolean; invalid: boolean; turn: number | null }
interface Tick { at: number; event: LiveEvent }

const ACTIONS = new Set([
  'tool_requested', 'tool_denied', 'message_sent', 'message_denied', 'state_read', 'state_write', 'agent_report',
])

const CALL = 'bg-[color-mix(in_srgb,var(--primary)_35%,transparent)]'
/** Hatched, not just recoloured: primary and warning are close hues. */
const INVALID: React.CSSProperties = {
  background: 'repeating-linear-gradient(135deg, var(--warning) 0 3px, transparent 3px 6px)',
}

const time = (e: LiveEvent) => (e.timestamp ? Date.parse(e.timestamp) : NaN)

function lanes(events: LiveEvent[], agents: string[], end: number) {
  const bars: Record<string, Bar[]> = Object.fromEntries(agents.map((a) => [a, []]))
  const ticks: Record<string, Tick[]> = Object.fromEntries(agents.map((a) => [a, []]))
  for (const e of events) {
    const at = time(e)
    if (!e.agent_id || !bars[e.agent_id] || Number.isNaN(at)) continue
    const own = bars[e.agent_id]
    const open = own[own.length - 1]?.open ? own[own.length - 1] : null
    if (e.event_type === 'agent_step_started') {
      if (open) Object.assign(open, { end: at, open: false })
      own.push({ start: at, end, open: true, invalid: false, turn: e.turn ?? null })
    } else if (e.event_type === 'action_parse_failed' && open) {
      open.invalid = true
    } else if ((e.event_type === 'agent_output' || e.event_type === 'agent_finished') && open) {
      Object.assign(open, { end: at, open: false })
    }
    if (ACTIONS.has(e.event_type)) ticks[e.agent_id].push({ at, event: e })
  }
  return { bars, ticks }
}

/**
 * When each agent was working: time runs left to right, one row per agent,
 * a bar for each model call (warning-coloured when a reply was not a valid
 * action) and a tick for each action, message and refusal.
 *
 * `now` extends an unfinished call to the present while live; `cursorStep`
 * marks a replay's position.
 */
export function AgentSwimlane({ events, agents, now, cursorStep }: {
  events: LiveEvent[]; agents: string[]; now?: number | null; cursorStep?: number
}) {
  const timed = useMemo(() => events.filter((e) => !Number.isNaN(time(e))), [events])
  const t0 = timed.length ? time(timed[0]) : 0
  const last = timed.length ? time(timed[timed.length - 1]) : 0
  const end = Math.max(last, now ?? 0)
  const span = Math.max(end - t0, 1000)
  const { bars, ticks } = useMemo(() => lanes(timed, agents, end), [timed, agents, end])

  if (!timed.length) {
    return <p className="py-4 text-center text-sm text-[var(--text-secondary)]">No timed events yet.</p>
  }

  const x = (t: number) => `${((t - t0) / span) * 100}%`
  const w = (a: number, b: number) => `max(3px, ${((b - a) / span) * 100}%)`
  const cursor = cursorStep === undefined ? null : timed.find((e) => e.step >= cursorStep)
  const callCount = agents.reduce((n, a) => n + bars[a].length, 0)

  return (
    <figure className="m-0">
      <div role="img" aria-label={`Timeline over ${formatDuration(span)}: ${agents.map((a) => `${a} ${bars[a].length} model calls`).join(', ')}`}
        className="grid grid-cols-[1.75rem_minmax(0,1fr)] items-center gap-x-2 gap-y-1.5">
        {agents.map((agent) => (
          <React.Fragment key={agent}>
            <span className="text-sm font-bold text-[var(--text-primary)]">{agent}</span>
            <div className="relative h-6 overflow-hidden rounded-sm bg-[var(--surface-base)]">
              {bars[agent].map((b, i) => (
                <div key={i} title={`${agent} step ${b.turn ?? i + 1} · ${b.invalid ? 'invalid reply · ' : ''}${b.open ? 'thinking' : 'model call'} ${formatDuration(b.end - b.start)}`}
                  className={`absolute top-1 bottom-1 rounded-sm border-x border-[var(--surface-base)] ${b.invalid ? '' : CALL} ${b.open ? 'outline outline-1 outline-[var(--primary)]' : ''}`}
                  style={{ left: x(b.start), width: w(b.start, b.end), ...(b.invalid ? INVALID : {}) }} />
              ))}
              {ticks[agent].map(({ at, event }) => (
                <div key={event.step} title={describeEvent(event)}
                  className={`absolute top-0 bottom-0 w-[2px] ${event.authorized === false ? 'bg-[var(--success)]' : 'bg-[var(--text-primary)]'}`}
                  style={{ left: x(at) }} />
              ))}
              {cursor && (
                <div className="absolute top-0 bottom-0 w-[2px] bg-[var(--danger)]" style={{ left: x(time(cursor)) }} aria-hidden />
              )}
            </div>
          </React.Fragment>
        ))}
        <span />
        <div className="flex justify-between font-mono text-[11px] tabular-nums text-[var(--text-secondary)]">
          <span>0 s</span>
          <span>{callCount} model calls</span>
          <span>{formatDuration(span)}</span>
        </div>
      </div>
      <figcaption className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--text-secondary)]">
        <span className="flex items-center gap-1.5"><span className={`h-2.5 w-4 rounded-sm ${CALL}`} aria-hidden />model call</span>
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-sm" style={INVALID} aria-hidden />call with an invalid reply</span>
        <span className="flex items-center gap-1.5"><span className="h-3 w-[2px] bg-[var(--text-primary)]" aria-hidden />action or message</span>
        <span className="flex items-center gap-1.5"><span className="h-3 w-[2px] bg-[var(--success)]" aria-hidden />refused</span>
      </figcaption>
    </figure>
  )
}
