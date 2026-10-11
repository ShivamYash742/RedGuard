"use client"
import React, { useState, useEffect } from 'react'
import { benchmarkDataService, LeaderboardRow, RateCI, OUTCOME_TIERS } from '@/lib/data-service'
import { Award, BarChart2, TrendingUp, Info } from 'lucide-react'
import EmptyState from '@/components/EmptyState'
import TierBar from '@/components/TierBar'
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts'

const pct = (x: number) => `${(x * 100).toFixed(1)}%`

function Rate({ value, tone }: { value: RateCI | null; tone: string }) {
  if (!value) return <span className="text-[var(--text-muted)]">n/a</span>
  return (
    <span className="font-mono">
      <span className={`font-bold ${tone}`}>{pct(value.rate)}</span>
      <span className="block text-[10px] text-[var(--text-muted)]">95% CI {pct(value.lo)}–{pct(value.hi)}</span>
    </span>
  )
}

const label = (r: LeaderboardRow) => `${r.agentName} · ${r.promptMode ?? 'agent default'}`
const titleCase = (s: string) => s.toLowerCase().replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())

export default function ModelsPage() {
  const [rows, setRows] = useState<LeaderboardRow[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    benchmarkDataService.fetchLeaderboard()
      .then(setRows)
      .finally(() => setLoading(false))
  }, [])

  const radarRows = rows.slice(0, 5)
  const families = Array.from(new Set(rows.flatMap(r => Object.keys(r.families)))).sort()
  const radarData = families.map(fam => {
    const entry: Record<string, string | number> = { family: titleCase(fam) }
    radarRows.forEach(r => {
      const f = r.families[fam]
      if (f && f.total > 0) entry[label(r)] = Math.round(100 * (1 - f.modelCompromised / f.total))
    })
    return entry
  })

  const tierShareData = rows.map(r => {
    const entry: Record<string, string | number> = { name: label(r) }
    OUTCOME_TIERS.forEach(t => { entry[t.label] = r.attacks > 0 ? Math.round((100 * r.tiers[t.key]) / r.attacks) : 0 })
    return entry
  })

  const colors = ['#9a6324', '#157a6e', '#a16207', '#c23616', '#44576b']

  if (loading) return <div className="p-8 text-center text-xs">Loading model leaderboard...</div>

  return (
    <div className="space-y-8">
      <div className="border-b border-[var(--border-subtle)] pb-4">
        <div className="flex items-center gap-2 text-xs font-semibold text-[var(--primary)] uppercase tracking-wider mb-1">
          <Award className="h-4 w-4 text-amber-500" /> Model Security Leaderboard
        </div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-tight">Models</h1>
        <p className="text-xs text-[var(--text-secondary)] mt-0.5">
          Measured results only, one row per agent and system-prompt mode, pooled over its completed runs.
          Ranked by attack success with the regex filter off (model alone); lower is better.
        </p>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="No measured runs yet"
          description="Runs from before tiered scoring are not comparable and are left out. Start an evaluation to see real numbers here."
          actionLabel="Go to Runs"
          actionHref="/runs"
          icon="chart"
        />
      ) : (
        <>
          <div className="overflow-x-auto rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)]">
            <table className="research-table">
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Agent · Prompt</th>
                  <th>Runs</th>
                  <th title="Share of attack probes the model complied with, filter off">ASR, model alone</th>
                  <th title="Share of attack probes that succeeded with the regex filter in front">ASR, as deployed</th>
                  <th>Outcome (F · R · I · C)</th>
                  <th title="Share of harmless control prompts the model refused">Over-refusal</th>
                  <th title="Behaviour Drift Score: 1 = same outcome every run. Needs 3+ runs.">BDS</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(r => (
                  <tr key={`${r.agentId}-${r.promptMode}`} className="hover:bg-[var(--surface-base)] transition-colors">
                    <td className="font-mono text-xs font-bold text-center">#{r.rank}</td>
                    <td className="text-xs">
                      <span className="font-bold text-[var(--text-primary)]">{r.agentName}</span>
                      <span className="block text-[10px] text-[var(--text-muted)]">
                        {r.promptMode ?? 'agent default'} · last run {new Date(r.lastRun).toLocaleDateString()}
                      </span>
                    </td>
                    <td className="font-mono text-xs text-center">{r.runs}</td>
                    <td className="text-xs"><Rate value={r.asrModel} tone="text-[var(--danger)]" /></td>
                    <td className="text-xs"><Rate value={r.asrDeployed} tone="text-[var(--danger)]" /></td>
                    <td className="font-mono text-xs min-w-[9rem]">
                      <TierBar counts={r.tiers} total={r.attacks} height="h-1.5" />
                      <span className="block mt-1 text-center">
                        {r.tiers.FILTERED} · {r.tiers.REFUSED} · {r.tiers.IGNORED} · <span className="text-[var(--danger)] font-bold">{r.tiers.COMPROMISED}</span>
                      </span>
                    </td>
                    <td className="text-xs"><Rate value={r.overRefusal} tone="text-[var(--warning)]" /></td>
                    <td className="font-mono text-xs text-center">{r.bds === null ? <span className="text-[var(--text-muted)]">n/a</span> : r.bds.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="research-card space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider flex items-center gap-1.5">
                  <BarChart2 className="h-4 w-4 text-[var(--primary)]" /> Resistance by attack family
                </h3>
                <div className="flex items-center gap-1 text-[11px] text-[var(--text-muted)] font-mono">
                  <Info className="h-3.5 w-3.5" /> % not compromised, model alone · top 5
                </div>
              </div>
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart cx="50%" cy="50%" outerRadius="62%" data={radarData}>
                    <PolarGrid stroke="var(--border-default)" opacity={0.4} />
                    <PolarAngleAxis dataKey="family" tick={{ fill: 'var(--text-secondary)', fontSize: 10 }} />
                    <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: 'var(--text-muted)', fontSize: 9 }} />
                    {radarRows.map((r, idx) => (
                      <Radar
                        key={label(r)}
                        name={label(r)}
                        dataKey={label(r)}
                        stroke={colors[idx % colors.length]}
                        fill={colors[idx % colors.length]}
                        fillOpacity={0.15}
                      />
                    ))}
                    <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                    <Tooltip contentStyle={{ backgroundColor: 'var(--surface-overlay)', borderColor: 'var(--border-default)', fontSize: '11px' }} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="research-card space-y-3">
              <h3 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider flex items-center gap-1.5">
                <TrendingUp className="h-4 w-4 text-[var(--success)]" /> Where attacks ended (% of attack probes)
              </h3>
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={tierShareData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                    <XAxis dataKey="name" tick={{ fill: 'var(--text-secondary)', fontSize: 10 }} />
                    <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 10 }} domain={[0, 100]} />
                    <Tooltip contentStyle={{ backgroundColor: 'var(--surface-overlay)', borderColor: 'var(--border-default)', fontSize: '11px' }} />
                    <Legend wrapperStyle={{ fontSize: '11px' }} />
                    {OUTCOME_TIERS.map(t => (
                      <Bar key={t.key} dataKey={t.label} stackId="a" fill={t.color} />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
