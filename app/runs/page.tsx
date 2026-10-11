"use client"
import React, { useState, useEffect, useMemo } from 'react'
import Link from 'next/link'
import { Play, RefreshCw, FileText, Shield, Bot, Wrench, ArrowRight, History } from 'lucide-react'
import { benchmarkDataService, normalizeFamily, KNOWN_AGENTS, KnownAgent, BenchmarkRun, OUTCOME_TIERS, TierCounts, emptyTierCounts, ControlCounts, emptyControlCounts } from '@/lib/data-service'
import TierBar from '@/components/TierBar'
import EmptyState from '@/components/EmptyState'
import { TableSkeleton } from '@/components/Skeletons'

interface FamilyProgress {
  name: string
  total: number
  current: number
  controls: number
  counts: TierCounts
  controlCounts: ControlCounts
}

type PromptMode = 'baseline' | 'hardened'

export default function RunsPage() {
  const [running, setRunning] = useState(false)
  const [families, setFamilies] = useState<FamilyProgress[]>([])
  const [progress, setProgress] = useState({ current: 0, total: 0 })
  const [promptMode, setPromptMode] = useState<PromptMode>('baseline')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [selectedAgent, setSelectedAgent] = useState<string>('nemotron_3_ultra')
  const [activeCategory, setActiveCategory] = useState<'nvidia' | 'ollama' | 'custom'>('nvidia')
  const [agents, setAgents] = useState<KnownAgent[]>(KNOWN_AGENTS)

  const [sessions, setSessions] = useState<BenchmarkRun[]>([])
  const [historyLoading, setHistoryLoading] = useState(true)

  const allFamilies = benchmarkDataService.getAttackFamilies()
  const [selectedFamilies, setSelectedFamilies] = useState<string[]>(allFamilies.map(f => f.id))

  useEffect(() => {
    benchmarkDataService.fetchAgents().then(data => {
      if (data && data.length > 0) {
        // Merge real configured agents with the known badge/category metadata where ids match.
        const merged: KnownAgent[] = data.map(a => {
          const known = KNOWN_AGENTS.find(k => k.id === a.id)
          return known || { id: a.id, name: a.name || a.id, badge: 'Configured Agent', category: 'custom' as const }
        })
        setAgents(merged)
      }
    })
  }, [])

  useEffect(() => {
    async function loadHistory() {
      try {
        const data = await benchmarkDataService.fetchSessions()
        setSessions(data)
      } catch (err) {
        console.error('Failed to load run history:', err)
      } finally {
        setHistoryLoading(false)
      }
    }
    loadHistory()
  }, [])

  // Probes the selected families will run; the server's count takes over once a run starts
  const plannedTotal = useMemo(() => benchmarkDataService.getAllProbes().filter(p =>
    selectedFamilies.length === 0 || selectedFamilies.some(f => normalizeFamily(f) === normalizeFamily(p.attack_family))
  ).length, [selectedFamilies])
  const displayTotal = running ? progress.total : plannedTotal


  const startScan = async () => {
    setRunning(true)
    setFamilies([])
    setProgress(p => ({ ...p, current: 0 }))
    setSessionId(null)

    try {
      const res = await fetch('/api/scan/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agentId: selectedAgent, promptMode }),
      })
      const data = await res.json()
      setSessionId(data.sessionId)

      let fams: FamilyProgress[] = []
      if (data.families) {
        fams = Object.entries(data.families)
          .filter(([name]) => selectedFamilies.length === 0 || selectedFamilies.some(f => normalizeFamily(f) === normalizeFamily(name)))
          .map(([name, total]) => ({
            name,
            total: total as number,
            current: 0,
            controls: data.controls?.[name] ?? 0,
            counts: emptyTierCounts(),
            controlCounts: emptyControlCounts(),
          }))
        setFamilies(fams)
      }

      const activeTotal = fams.reduce((acc, f) => acc + f.total, 0)
      setProgress(p => ({ ...p, total: activeTotal }))

      let overallCurrent = 0

      for (let i = 0; i < fams.length; i++) {
        const familyName = fams[i].name

        const result = await new Promise<string | void>((resolve) => {
          const evtSource = new EventSource(`/api/scan/family?sessionId=${data.sessionId}&agentId=${selectedAgent}&category=${familyName}`)

          evtSource.addEventListener('probe_result', (e) => {
            const payload = JSON.parse(e.data)
            overallCurrent += 1
            setProgress(p => ({ ...p, current: overallCurrent }))

            setFamilies(prev => {
              const updated = [...prev]
              updated[i] = { ...updated[i], current: payload.index, counts: payload.counts, controlCounts: payload.controls }
              return updated
            })
          })

          evtSource.addEventListener('family_complete', (e) => {
            const payload = JSON.parse(e.data)
            setFamilies(prev => {
              const updated = [...prev]
              updated[i] = { ...updated[i], counts: payload.counts, controlCounts: payload.controls }
              return updated
            })
            evtSource.close()
            resolve()
          })

          evtSource.addEventListener('error', (e: Event) => {
            try {
              const msgEvent = e as MessageEvent
              const payload = JSON.parse(msgEvent.data)
              console.error("Agent API error:", payload.message)
            } catch { }
            evtSource.close()
            resolve('error')
          })

          evtSource.onerror = () => {
            evtSource.close()
            resolve('error')
          }
        })

        if (result === 'error') {
          break
        }
      }

      await fetch('/api/scan/finalize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessionId: data.sessionId }),
      })

      benchmarkDataService.invalidateCache()
      const refreshed = await benchmarkDataService.fetchSessions()
      setSessions(refreshed)
      setRunning(false)
    } catch (err) {
      console.error(err)
      setRunning(false)
    }
  }

  const isComplete = !running && sessionId && progress.current > 0
  const overallCounts = families.reduce((acc, f) => {
    OUTCOME_TIERS.forEach(t => { acc[t.key] += f.counts[t.key] })
    return acc
  }, emptyTierCounts())
  const attackTotal = families.reduce((acc, f) => acc + f.total - f.controls, 0)
  const controlTotal = families.reduce((acc, f) => acc + f.controls, 0)
  const overallControls = families.reduce((acc, f) => ({
    FILTERED: acc.FILTERED + f.controlCounts.FILTERED,
    OVER_REFUSED: acc.OVER_REFUSED + f.controlCounts.OVER_REFUSED,
    HELPED: acc.HELPED + f.controlCounts.HELPED,
  }), emptyControlCounts())
  const agentsByCategory = agents.filter(a => a.category === activeCategory)

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[var(--border-subtle)] pb-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold text-[var(--primary)] uppercase tracking-wider mb-1">
            <Play className="h-4 w-4 fill-current" /> Live Execution Suite
          </div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-tight">Runs</h1>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Launch a new evaluation against a target agent, or review a past run below.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {isComplete && (
            <Link
              href={`/runs/${sessionId}`}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-[var(--radius)] bg-[var(--success)] text-white text-xs font-semibold shadow-xs hover:opacity-90 transition-opacity"
            >
              <FileText className="h-4 w-4" /> View Run Report
            </Link>
          )}

          <button
            onClick={startScan}
            disabled={running}
            className={`inline-flex items-center gap-2 px-5 py-2 rounded-[var(--radius)] text-xs font-bold text-[var(--primary-foreground)] shadow-xs transition-all ${running ? 'bg-[var(--primary)]/60 cursor-not-allowed' : 'bg-[var(--primary)] hover:bg-[var(--primary-hover)] cursor-pointer'
              }`}
          >
            {running ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4 fill-current" />}
            {running ? 'Evaluating Probes...' : 'Start Evaluation Run'}
          </button>
        </div>
      </div>

      {/* Target Agent & Configuration Panel */}
      <div className="research-card space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider">Target Model & Agent Selection</h2>
          <span className="font-mono text-[11px] text-[var(--text-muted)]">Benchmark Version: v4.0.0</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {([
            { key: 'nvidia' as const, icon: Shield, label: 'NVIDIA NIM Guards', sub: 'Nemotron, Llama-3.3, DeepSeek' },
            { key: 'ollama' as const, icon: Bot, label: 'Local Ollama Runner', sub: 'Local mistral / llama endpoints' },
            { key: 'custom' as const, icon: Wrench, label: 'Custom Template Agent', sub: 'Python backend custom agent' },
          ]).map(cat => (
            <button
              key={cat.key}
              onClick={() => !running && setActiveCategory(cat.key)}
              className={`p-3 rounded-[var(--radius)] border text-left text-xs font-semibold transition-all ${activeCategory === cat.key
                  ? 'border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--primary)]'
                  : 'border-[var(--border-subtle)] bg-[var(--surface-base)] text-[var(--text-secondary)] hover:border-[var(--border-default)]'
                }`}
            >
              <span className="flex items-center gap-1.5"><cat.icon className="h-3.5 w-3.5" /> {cat.label}</span>
              <span className="block text-[10px] font-normal text-[var(--text-muted)] mt-1">{cat.sub}</span>
            </button>
          ))}
        </div>

        <div className="p-3 bg-[var(--surface-base)] rounded-[var(--radius)] border border-[var(--border-subtle)] space-y-2">
          <span className="text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider block">
            Select Evaluation Target Model ({agentsByCategory.length} in this category)
          </span>
          <div className="flex flex-wrap gap-2">
            {agentsByCategory.map((agent) => (
              <button
                key={agent.id}
                onClick={() => !running && setSelectedAgent(agent.id)}
                className={`px-3 py-1.5 rounded-[var(--radius)] text-xs font-medium border transition-colors flex items-center gap-1.5 ${selectedAgent === agent.id
                    ? 'bg-[var(--primary)] text-[var(--primary-foreground)] border-[var(--primary)] font-semibold shadow-xs'
                    : 'bg-[var(--surface-raised)] border-[var(--border-subtle)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                  }`}
              >
                <span>{agent.name}</span>
                <span className={`text-[9px] font-mono px-1.5 py-0.2 rounded ${selectedAgent === agent.id ? 'bg-black/10 text-[var(--primary-foreground)]' : 'bg-[var(--surface-base)] text-[var(--text-muted)] border border-[var(--border-subtle)]'
                  }`}>
                  {agent.badge}
                </span>
              </button>
            ))}
          </div>
        </div>

        <div className="p-3 bg-[var(--surface-base)] rounded-[var(--radius)] border border-[var(--border-subtle)] space-y-2">
          <span className="text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider block">System Prompt</span>
          <div className="flex flex-wrap gap-2">
            {([
              { key: 'baseline' as const, label: 'Baseline', sub: 'Neutral prompt — compares models fairly' },
              { key: 'hardened' as const, label: 'Hardened', sub: 'Prompt that lists the attack families — measures the prompt as a defence' },
            ]).map(m => (
              <button
                key={m.key}
                onClick={() => !running && setPromptMode(m.key)}
                aria-pressed={promptMode === m.key}
                className={`px-3 py-1.5 rounded-[var(--radius)] text-xs border text-left transition-colors ${promptMode === m.key
                    ? 'bg-[var(--primary)]/15 border-[var(--primary)] text-[var(--primary)] font-semibold'
                    : 'bg-[var(--surface-raised)] border-[var(--border-subtle)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                  }`}
              >
                {m.label}
                <span className="block text-[10px] font-normal text-[var(--text-muted)]">{m.sub}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="p-3 bg-[var(--surface-base)] rounded-[var(--radius)] border border-[var(--border-subtle)] space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider block">
              Target Attack Families Scope ({selectedFamilies.length} / {allFamilies.length} Selected)
            </span>
            <button
              onClick={() => setSelectedFamilies(selectedFamilies.length === allFamilies.length ? [] : allFamilies.map(f => f.id))}
              className="text-[11px] text-[var(--primary)] font-semibold hover:underline"
            >
              {selectedFamilies.length === allFamilies.length ? 'Deselect All' : `Select All ${allFamilies.length} Families`}
            </button>
          </div>

          <div className="flex flex-wrap gap-2">
            {allFamilies.map((fam) => {
              const isSelected = selectedFamilies.includes(fam.id)
              return (
                <button
                  key={fam.id}
                  onClick={() => {
                    if (running) return
                    setSelectedFamilies(isSelected ? selectedFamilies.filter(id => id !== fam.id) : [...selectedFamilies, fam.id])
                  }}
                  className={`px-2.5 py-1 rounded-[var(--radius)] text-xs font-medium border transition-colors ${isSelected
                      ? 'bg-[var(--primary)]/15 border-[var(--primary)] text-[var(--primary)] font-semibold'
                      : 'bg-[var(--surface-raised)] border-[var(--border-subtle)] text-[var(--text-muted)] opacity-60'
                    }`}
                >
                  {isSelected ? '✓ ' : '+ '}{fam.name}
                </button>
              )
            })}
          </div>
        </div>
      </div>

      {/* Live SSE Progress Overview Bar */}
      <div className="research-card space-y-3">
        <div className="flex items-center justify-between text-xs font-semibold text-[var(--text-primary)]">
          <div className="flex items-center gap-2">
            <span>Evaluation Progress:</span>
            <span className="font-mono text-sm font-bold text-[var(--primary)]">{progress.current} / {displayTotal}</span>
          </div>
        </div>

        <TierBar counts={overallCounts} total={attackTotal} />

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {OUTCOME_TIERS.map(t => (
            <div key={t.key} className="p-2 rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-base)]">
              <span className="flex items-center gap-1.5 text-[11px] font-semibold text-[var(--text-secondary)]">
                <span className="h-2.5 w-2.5 rounded-sm shrink-0" style={{ background: t.color }} />
                {t.label}
              </span>
              <span className="block font-mono text-lg font-bold text-[var(--text-primary)]">{overallCounts[t.key]}</span>
              <span className="block text-[10px] text-[var(--text-muted)]">{t.hint}</span>
            </div>
          ))}
        </div>

        {controlTotal > 0 && (
          <p className="text-[11px] text-[var(--text-secondary)] font-mono">
            Benign controls ({controlTotal}): {overallControls.HELPED} helped · {overallControls.OVER_REFUSED} over-refused by the model · {overallControls.FILTERED} blocked by the regex
          </p>
        )}
      </div>

      {families.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {families.map((f, idx) => {
            const isActive = running && f.current > 0 && f.current < f.total
            return (
              <div key={idx} className={`research-card transition-all ${isActive ? 'active-scan-pulse border-[var(--primary)]' : ''}`}>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-xs font-bold text-[var(--text-primary)] capitalize">{f.name.replace(/_/g, ' ')}</h3>
                  <span className="font-mono text-[11px] text-[var(--text-muted)]">{f.current} / {f.total}</span>
                </div>
                <div className="mb-3">
                  <TierBar counts={f.counts} total={f.total - f.controls} height="h-2" />
                </div>
                <div className="grid grid-cols-4 gap-1 text-[11px] font-mono text-center">
                  {OUTCOME_TIERS.map(t => (
                    <span key={t.key} title={t.label} className={t.key === 'COMPROMISED' ? 'text-[var(--danger)] font-bold' : 'text-[var(--text-secondary)]'}>
                      {t.label[0]} {f.counts[t.key]}
                    </span>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Run History */}
      <div className="space-y-3 pt-2">
        <h2 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider flex items-center gap-1.5">
          <History className="h-4 w-4 text-[var(--primary)]" /> Run History
        </h2>

        {historyLoading ? (
          <TableSkeleton rows={5} />
        ) : sessions.length === 0 ? (
          <EmptyState
            title="No evaluation runs recorded"
            description="Start your first benchmark evaluation run above to populate history."
            icon="play"
          />
        ) : (
          <div className="overflow-x-auto rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)]">
            <table className="research-table">
              <thead>
                <tr>
                  <th>Run / Session ID</th>
                  <th>Execution Date & Time</th>
                  <th>Target Agent</th>
                  <th>Probes Fired</th>
                  <th>Outcome (F · R · I · C)</th>
                  <th>Security Rate</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((s) => {
                  const score = s.totalProbes > 0 ? ((s.blocked / s.totalProbes) * 100).toFixed(1) : '0.0'
                  return (
                    <tr key={s.id} className="hover:bg-[var(--surface-base)] transition-colors">
                      <td className="font-mono text-xs font-bold text-[var(--text-primary)]">{s.sessionId}</td>
                      <td className="text-xs text-[var(--text-secondary)]">{new Date(s.startedAt).toLocaleString()}</td>
                      <td className="font-semibold text-xs text-[var(--text-primary)]">
                        {s.agentName}
                        <span className="block text-[10px] font-normal text-[var(--text-muted)]">{s.promptMode ?? 'legacy scoring'}</span>
                      </td>
                      <td className="font-mono text-xs text-center">{s.totalProbes}</td>
                      <td className="font-mono text-xs text-center min-w-[9rem]">
                        {s.tiers ? (
                          <>
                            <TierBar counts={s.tiers} total={s.totalProbes} height="h-1.5" />
                            <span className="block mt-1">
                              {s.tiers.FILTERED} · {s.tiers.REFUSED} · {s.tiers.IGNORED} · <span className="text-[var(--danger)] font-bold">{s.tiers.COMPROMISED}</span>
                            </span>
                          </>
                        ) : (
                          <span className="text-[var(--text-muted)]">{s.blocked} resisted</span>
                        )}
                      </td>
                      <td className="font-mono text-xs text-center font-extrabold text-[var(--primary)]">{score}%</td>
                      <td><span className="badge-semantic badge-success">{s.status}</span></td>
                      <td>
                        <Link href={`/runs/${s.sessionId}`} className="inline-flex items-center gap-1 text-xs text-[var(--primary)] font-semibold hover:underline">
                          Open Report <ArrowRight className="h-3 w-3" />
                        </Link>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
