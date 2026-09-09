"use client"
import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import { Play, CheckCircle2, AlertTriangle, ShieldCheck, RefreshCw, FileText, ArrowRight } from 'lucide-react'
import { benchmarkDataService, normalizeFamily } from '@/lib/data-service'

interface FamilyProgress {
  name: string
  total: number
  current: number
  blocked: number
  allowed: number
}

export default function BenchmarkPage() {
  const [running, setRunning] = useState(false)
  const [families, setFamilies] = useState<FamilyProgress[]>([])
  const [progress, setProgress] = useState({ current: 0, total: 0, blocked: 0, allowed: 0 })
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [selectedAgent, setSelectedAgent] = useState<string>('nemotron_3_ultra')
  const [activeCategory, setActiveCategory] = useState<'nvidia' | 'ollama' | 'custom'>('nvidia')
  const [agents, setAgents] = useState<any[]>([])
  const [reconnecting, setReconnecting] = useState(false)

  // Filters
  const [selectedFamilies, setSelectedFamilies] = useState<string[]>([
    'direct_injection', 'content_injection', 'exfiltration', 'goal_diversion',
    'memory_poisoning', 'autonomy', 'planning', 'tool_security'
  ])

  useEffect(() => {
    benchmarkDataService.fetchAgents().then(data => {
      if (data && data.length > 0) setAgents(data)
    })

    benchmarkDataService.fetchStats().then(stats => {
      if (stats) setProgress(p => ({ ...p, total: stats.totalProbes || 128 }))
    })
  }, [])

  const startScan = async () => {
    setRunning(true)
    setFamilies([])
    setProgress(p => ({ ...p, current: 0, blocked: 0, allowed: 0 }))
    setSessionId(null)

    try {
      // 1. Start scan session
      const res = await fetch('/api/scan/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agentId: selectedAgent }),
      })
      const data = await res.json()
      setSessionId(data.sessionId)
      setProgress(p => ({ ...p, total: data.total_probes }))

      let fams: FamilyProgress[] = []
      if (data.families) {
        fams = Object.entries(data.families)
          .filter(([name]) => selectedFamilies.length === 0 || selectedFamilies.some(f => normalizeFamily(f) === normalizeFamily(name)))
          .map(([name, total]) => ({
            name,
            total: total as number,
            current: 0,
            blocked: 0,
            allowed: 0,
          }))
        setFamilies(fams)
      }

      // 2. Stream family scans
      let overallBlocked = 0
      let overallAllowed = 0
      let overallCurrent = 0

      for (let i = 0; i < fams.length; i++) {
        const familyName = fams[i].name

        await new Promise<void>((resolve) => {
          const evtSource = new EventSource(`/api/scan/family?sessionId=${data.sessionId}&agentId=${selectedAgent}&category=${familyName}`)

          evtSource.addEventListener('probe_result', (e) => {
            const payload = JSON.parse(e.data)
            overallCurrent += 1
            setProgress(p => ({ ...p, current: overallCurrent }))

            setFamilies(prev => {
              const updated = [...prev]
              updated[i] = {
                ...updated[i],
                current: payload.index,
                blocked: payload.blocked,
                allowed: payload.allowed,
              }
              return updated
            })
          })

          evtSource.addEventListener('family_complete', (e) => {
            const payload = JSON.parse(e.data)
            overallBlocked += payload.blocked
            overallAllowed += payload.allowed

            setProgress(p => ({
              ...p,
              blocked: overallBlocked,
              allowed: overallAllowed,
            }))

            setFamilies(prev => {
              const updated = [...prev]
              updated[i] = {
                ...updated[i],
                blocked: payload.blocked,
                allowed: payload.allowed,
              }
              return updated
            })

            evtSource.close()
            resolve()
          })

          evtSource.onerror = () => {
            evtSource.close()
            resolve()
          }
        })
      }

      // 3. Finalize scan
      await fetch('/api/scan/finalize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessionId: data.sessionId }),
      })

      benchmarkDataService.invalidateCache()
      setRunning(false)
    } catch (err) {
      console.error(err)
      setRunning(false)
    }
  }

  const isComplete = !running && sessionId && progress.current > 0

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[var(--border-subtle)] pb-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold text-[var(--primary)] uppercase tracking-wider mb-1">
            <Play className="h-4 w-4 fill-current" /> Live Execution Suite
          </div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-tight">Run AI Benchmark Evaluation</h1>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Configure dataset parameters and execute real-time security probes against target model endpoints.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {isComplete && (
            <Link
              href={`/reports?session=${sessionId}`}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-emerald-600 text-white text-xs font-semibold shadow-xs hover:bg-emerald-700 transition-colors"
            >
              <FileText className="h-4 w-4" /> View Benchmark Report
            </Link>
          )}

          <button
            onClick={startScan}
            disabled={running}
            className={`inline-flex items-center gap-2 px-5 py-2 rounded-md text-xs font-bold text-white shadow-xs transition-all ${
              running
                ? 'bg-blue-400 cursor-not-allowed opacity-75'
                : 'bg-[var(--primary)] hover:bg-[var(--primary-hover)] cursor-pointer'
            }`}
          >
            {running ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4 fill-current" />}
            {running ? 'Evaluating Probes...' : '▶ Start Evaluation Run'}
          </button>
        </div>
      </div>

      {/* Target Agent & Configuration Panel */}
      <div className="research-card space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider">Target Model & Agent Selection</h2>
          <span className="font-mono text-[11px] text-[var(--text-muted)]">Benchmark Version: v2.5.0</span>
        </div>

        {/* Agent Category Selector */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <button
            onClick={() => !running && setActiveCategory('nvidia')}
            className={`p-3 rounded-lg border text-left text-xs font-semibold transition-all ${
              activeCategory === 'nvidia'
                ? 'border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--primary)]'
                : 'border-[var(--border-subtle)] bg-[var(--surface-base)] text-[var(--text-secondary)] hover:border-[var(--border-default)]'
            }`}
          >
            🛡️ NVIDIA NIM Guards
            <span className="block text-[10px] font-normal text-[var(--text-muted)] mt-1">Nemotron, Llama-3.3, DeepSeek</span>
          </button>

          <button
            onClick={() => !running && setActiveCategory('ollama')}
            className={`p-3 rounded-lg border text-left text-xs font-semibold transition-all ${
              activeCategory === 'ollama'
                ? 'border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--primary)]'
                : 'border-[var(--border-subtle)] bg-[var(--surface-base)] text-[var(--text-secondary)] hover:border-[var(--border-default)]'
            }`}
          >
            🦙 Local Ollama Runner
            <span className="block text-[10px] font-normal text-[var(--text-muted)] mt-1">Local mistral / llama endpoints</span>
          </button>

          <button
            onClick={() => !running && setActiveCategory('custom')}
            className={`p-3 rounded-lg border text-left text-xs font-semibold transition-all ${
              activeCategory === 'custom'
                ? 'border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--primary)]'
                : 'border-[var(--border-subtle)] bg-[var(--surface-base)] text-[var(--text-secondary)] hover:border-[var(--border-default)]'
            }`}
          >
            🛠️ Custom Template Agent
            <span className="block text-[10px] font-normal text-[var(--text-muted)] mt-1">Python backend custom agent</span>
          </button>
        </div>

        {/* Specific Agent Sub-option selector */}
        <div className="p-3 bg-[var(--surface-base)] rounded-lg border border-[var(--border-subtle)] space-y-2">
          <span className="text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider block">
            Select Evaluation Target Model (5 Pre-configured Models + Custom)
          </span>
          <div className="flex flex-wrap gap-2">
            {[
              { id: 'nemotron_3_ultra', name: 'Nemotron-3 Ultra (550B)', badge: 'NVIDIA NIM' },
              { id: 'nemotron_super_agent', name: 'Nemotron-3 Super (120B)', badge: 'NVIDIA NIM' },
              { id: 'llama3_3_70b_agent', name: 'Llama 3.3 70B Instruct', badge: 'NVIDIA NIM' },
              { id: 'deepseek_flash_agent', name: 'DeepSeek Flash 2.5', badge: 'NVIDIA NIM' },
              { id: 'ollama_local_agent', name: 'Ollama Local Agent', badge: 'Local Ollama' },
              { id: 'example_custom_agent', name: 'Example Custom Agent', badge: 'Custom Template' },
            ].map((agent) => (
              <button
                key={agent.id}
                onClick={() => !running && setSelectedAgent(agent.id)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium border transition-colors flex items-center gap-1.5 ${
                  selectedAgent === agent.id
                    ? 'bg-[var(--primary)] text-white border-[var(--primary)] font-semibold shadow-xs'
                    : 'bg-[var(--surface-raised)] border-[var(--border-subtle)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                }`}
              >
                <span>{agent.name}</span>
                <span className={`text-[9px] font-mono px-1.5 py-0.2 rounded ${
                  selectedAgent === agent.id ? 'bg-white/20 text-white' : 'bg-[var(--surface-base)] text-[var(--text-muted)] border border-[var(--border-subtle)]'
                }`}>
                  {agent.badge}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Attack Family Multi-Select Filter Panel */}
        <div className="p-3 bg-[var(--surface-base)] rounded-lg border border-[var(--border-subtle)] space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider block">
              Target Attack Families Scope ({selectedFamilies.length} / 8 Selected)
            </span>
            <button
              onClick={() => {
                if (selectedFamilies.length === 8) {
                  setSelectedFamilies([])
                } else {
                  setSelectedFamilies(['direct_injection', 'content_injection', 'exfiltration', 'goal_diversion', 'memory_poisoning', 'autonomy', 'planning', 'tool_security'])
                }
              }}
              className="text-[11px] text-[var(--primary)] font-semibold hover:underline"
            >
              {selectedFamilies.length === 8 ? 'Deselect All' : 'Select All 8 Families'}
            </button>
          </div>

          <div className="flex flex-wrap gap-2">
            {[
              { id: 'direct_injection', label: 'Direct Injection' },
              { id: 'content_injection', label: 'Content Injection' },
              { id: 'exfiltration', label: 'Exfiltration' },
              { id: 'goal_diversion', label: 'Goal Diversion' },
              { id: 'memory_poisoning', label: 'Memory Poisoning' },
              { id: 'autonomy', label: 'Autonomy' },
              { id: 'planning', label: 'Planning' },
              { id: 'tool_security', label: 'Tool Security' },
            ].map((fam) => {
              const isSelected = selectedFamilies.includes(fam.id)
              return (
                <button
                  key={fam.id}
                  onClick={() => {
                    if (running) return
                    if (isSelected) {
                      setSelectedFamilies(selectedFamilies.filter(id => id !== fam.id))
                    } else {
                      setSelectedFamilies([...selectedFamilies, fam.id])
                    }
                  }}
                  className={`px-2.5 py-1 rounded-md text-xs font-medium border transition-colors ${
                    isSelected
                      ? 'bg-[var(--primary)]/15 border-[var(--primary)] text-[var(--primary)] font-semibold'
                      : 'bg-[var(--surface-raised)] border-[var(--border-subtle)] text-[var(--text-muted)] opacity-60'
                  }`}
                >
                  {isSelected ? '✓ ' : '+ '}{fam.label}
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
            <span className="font-mono text-sm font-bold text-[var(--primary)]">{progress.current} / {progress.total}</span>
            {reconnecting && (
              <span className="badge-semantic badge-warning animate-pulse">
                Reconnecting SSE...
              </span>
            )}
          </div>
          <div className="flex items-center gap-4 text-xs font-mono">
            <span className="text-emerald-600 dark:text-emerald-400 font-bold">Resisted: {progress.blocked}</span>
            <span className="text-rose-600 dark:text-rose-400 font-bold">Compromised: {progress.allowed}</span>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="h-3 w-full bg-[var(--surface-base)] rounded-full overflow-hidden border border-[var(--border-subtle)]">
          <div
            className="h-full bg-[var(--primary)] transition-all duration-300 ease-out"
            style={{ width: `${progress.total > 0 ? (progress.current / progress.total) * 100 : 0}%` }}
          />
        </div>
      </div>

      {/* Live Family Execution Grid */}
      {families.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {families.map((f, idx) => {
            const isFinished = f.current === f.total && f.total > 0
            const isActive = running && f.current > 0 && f.current < f.total
            return (
              <div
                key={idx}
                className={`research-card transition-all ${
                  isActive ? 'active-scan-pulse border-[var(--primary)]' : ''
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-xs font-bold text-[var(--text-primary)] capitalize">
                    {f.name.replace(/_/g, ' ')}
                  </h3>
                  <span className="font-mono text-[11px] text-[var(--text-muted)]">
                    {f.current} / {f.total}
                  </span>
                </div>

                <div className="h-2 w-full bg-[var(--surface-base)] rounded-full overflow-hidden mb-3 border border-[var(--border-subtle)]">
                  <div
                    className={`h-full transition-all duration-300 ${isFinished ? 'bg-emerald-500' : 'bg-[var(--primary)]'}`}
                    style={{ width: `${f.total > 0 ? (f.current / f.total) * 100 : 0}%` }}
                  />
                </div>

                <div className="flex items-center justify-between text-[11px] font-mono">
                  <span className="text-emerald-600 dark:text-emerald-400">Secure: {f.blocked}</span>
                  <span className="text-rose-600 dark:text-rose-400">Compromised: {f.allowed}</span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
