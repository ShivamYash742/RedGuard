"use client"
import React, { useEffect, useState } from 'react'
import { useReducedMotion } from 'framer-motion'
import { AGENT_ROLES, AgentTrack, RouteState, formatDuration, since } from '@/lib/lab-service'

/** `Date.now()`, re-read every `ms` while `ticking`. */
export function useNow(ticking: boolean, ms = 1000): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!ticking) return
    const id = setInterval(() => setNow(Date.now()), ms)
    return () => clearInterval(id)
  }, [ticking, ms])
  return now
}

export const FINISH_REASONS: Record<string, string> = {
  finish: 'called finish',
  parse_failure: 'gave up: no valid action',
  max_steps: 'used its whole step budget',
}

const TONES = {
  active: 'text-[var(--primary)]',
  warn: 'text-[var(--warning)]',
  quiet: 'text-[var(--text-secondary)]',
} as const

function status(track: AgentTrack, now: number, live: boolean): { text: string; tone: keyof typeof TONES } {
  const elapsed = live ? since(track.since, now) : null
  const timer = elapsed !== null ? ` ${formatDuration(elapsed)}` : ''
  switch (track.status) {
    case 'thinking':
      return { text: `thinking${timer}`, tone: 'active' }
    case 'retrying':
      return { text: `invalid reply, retrying${timer}`, tone: 'warn' }
    case 'acted':
      return { text: track.lastLatencyMs !== null ? `acted after ${formatDuration(track.lastLatencyMs)}` : 'acted', tone: 'active' }
    case 'finished':
      return {
        text: `finished · ${FINISH_REASONS[track.finishReason ?? ''] ?? track.finishReason ?? 'done'}`,
        tone: track.finishReason === 'finish' ? 'quiet' : 'warn',
      }
    default:
      return { text: 'waiting for upstream', tone: 'quiet' }
  }
}

/** One card per agent: what it is doing now, for how long, and how its run
 *  has gone so far. Agents run in sequence, so at most one is ever active. */
export function AgentCards({ agents, route, live }: { agents: string[]; route: RouteState; live: boolean }) {
  const now = useNow(live && agents.some((a) => route.agents[a]?.active))
  const reduced = useReducedMotion()

  return (
    <ul className="grid gap-2 sm:grid-cols-3" aria-label="Agents">
      {agents.map((agent) => {
        const track = route.agents[agent]
        if (!track) return null
        const s = status(track, now, live)
        const working = track.status === 'thinking' || track.status === 'retrying'
        return (
          <li key={agent}
            className={`min-w-0 rounded-[var(--radius)] border px-3 py-2.5 ${track.active
              ? 'border-[var(--primary)] bg-[color-mix(in_srgb,var(--primary)_6%,transparent)]'
              : 'border-[var(--border-subtle)] bg-[var(--surface-base)]'}`}>
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-sm text-[var(--text-primary)]">
                <span className="font-bold">{agent}</span>
                <span className="text-[var(--text-secondary)]"> · {AGENT_ROLES[agent] ?? 'agent'}</span>
              </span>
              {track.turn !== null && (
                <span className="font-mono text-xs tabular-nums text-[var(--text-secondary)]">
                  step {track.turn}{track.maxSteps ? ` of ${track.maxSteps}` : ''}
                </span>
              )}
            </div>
            <p className={`mt-1 flex items-center gap-1.5 text-sm font-semibold ${TONES[s.tone]}`} aria-live={track.active ? 'polite' : undefined}>
              {working && (
                <span className={`inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-current ${reduced ? '' : 'animate-pulse'}`} aria-hidden />
              )}
              <span className="truncate tabular-nums">{s.text}</span>
            </p>
            <p className="mt-1 truncate font-mono text-xs text-[var(--text-secondary)]" title={track.lastAction ?? undefined}>
              {track.lastAction ? (
                <>last: <span className={track.lastRefused ? 'text-[var(--success)]' : 'text-[var(--text-primary)]'}>
                  {track.lastRefused ? `refused · ${track.lastAction}` : track.lastAction}
                </span></>
              ) : 'no action yet'}
            </p>
            {(track.refused > 0 || track.invalid > 0) && (
              <p className="mt-1 flex gap-3 text-xs text-[var(--text-secondary)]">
                {track.refused > 0 && <span><span className="font-mono font-semibold tabular-nums text-[var(--text-primary)]">{track.refused}</span> refused</span>}
                {track.invalid > 0 && <span className="text-[var(--warning)]"><span className="font-mono font-semibold tabular-nums">{track.invalid}</span> invalid {track.invalid === 1 ? 'reply' : 'replies'}</span>}
              </p>
            )}
          </li>
        )
      })}
    </ul>
  )
}
