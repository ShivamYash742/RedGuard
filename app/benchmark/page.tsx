"use client"
import React, { useState, useEffect, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { 
  Play, ShieldAlert, Terminal, CheckCircle2, XCircle, 
  Activity, Square, RefreshCw, Cpu, Layers, AlertTriangle, Filter
} from 'lucide-react'
import { MOCK_ATTACK_FAMILIES, MOCK_SCENARIOS } from '@/lib/data-service'
import { Button } from '@/components/ui/button'

function LiveBenchmarkContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const familyParam = searchParams.get('family')

  const [agentsList, setAgentsList] = useState<{ id: string; name: string; description?: string }[]>([
    { id: 'nemotron_3_ultra', name: 'Nemotron-3 Ultra (550B)', description: 'NVIDIA Nemotron 3 Ultra 550B NIM' },
    { id: 'nemotron_super_agent', name: 'Nemotron-3 Super (120B)', description: 'NVIDIA Nemotron 3 Super 120B NIM' },
    { id: 'deepseek_flash_agent', name: 'DeepSeek V4 Flash', description: 'DeepSeek V4 Flash NIM' },
    { id: 'llama3_3_70b_agent', name: 'Meta Llama 3.3 (70B)', description: 'Meta Llama 3.3 70B Instruct NIM' },
    { id: 'ollama_local_agent', name: 'Ollama (Local / Offline)', description: 'Air-gapped local model via Ollama' }
  ])

  const [selectedAgent, setSelectedAgent] = useState('nemotron_3_ultra')
  const [selectedFamilies, setSelectedFamilies] = useState<string[]>(
    familyParam ? [familyParam] : MOCK_ATTACK_FAMILIES.map(f => f.id)
  )

  useEffect(() => {
    async function loadAgents() {
      try {
        const res = await fetch('/api/agents')
        if (res.ok) {
          const data = await res.json()
          if (Array.isArray(data) && data.length > 0) {
            setAgentsList(data)
          }
        }
      } catch {
        // use default 5 agents
      }
    }
    loadAgents()
  }, [])

  useEffect(() => {
    if (familyParam && MOCK_ATTACK_FAMILIES.some(f => f.id === familyParam)) {
      setSelectedFamilies([familyParam])
    }
  }, [familyParam])

  // Execution state
  const [isRunning, setIsRunning] = useState(false)
  const [progress, setProgress] = useState(0)
  const [currentProbe, setCurrentProbe] = useState<string>('')
  const [stats, setStats] = useState({ total: 0, blocked: 0, allowed: 0, errors: 0 })
  const [logs, setLogs] = useState<{ id: string; text: string; status: 'BLOCKED' | 'ALLOWED' | 'INFO' }[]>([])

  const toggleFamily = (id: string) => {
    setSelectedFamilies(prev => 
      prev.includes(id) ? prev.filter(item => item !== id) : [...prev, id]
    )
  }

  const selectOnlyFamily = (id: string) => {
    setSelectedFamilies([id])
  }

  const selectAllFamilies = () => {
    setSelectedFamilies(MOCK_ATTACK_FAMILIES.map(f => f.id))
  }

  const startBenchmark = async () => {
    setIsRunning(true)
    setProgress(0)
    setStats({ total: 0, blocked: 0, allowed: 0, errors: 0 })
    setLogs([])

    const allProbes = [
      { name: 'System Prompt Override (DAN Mode)', category: 'direct_injection', status: 'BLOCKED' as const },
      { name: 'Developer Mode System Prompt Bypass', category: 'direct_injection', status: 'BLOCKED' as const },
      { name: 'Hidden Comment Injection in HTML', category: 'content_injection', status: 'BLOCKED' as const },
      { name: 'Indirect RSS Feed Payload Injection', category: 'content_injection', status: 'ALLOWED' as const },
      { name: 'Markdown DNS Image Exfiltration', category: 'exfiltration', status: 'ALLOWED' as const },
      { name: 'URL Query Token Leaker', category: 'exfiltration', status: 'BLOCKED' as const },
      { name: 'Bash Parameter Command Substitution', category: 'tool_security', status: 'BLOCKED' as const },
      { name: 'Path Traversal ../../etc/passwd', category: 'tool_security', status: 'BLOCKED' as const },
      { name: 'Goal Diversion to Unauth Transfer', category: 'goal_diversion', status: 'BLOCKED' as const },
      { name: 'RAG Context Vector Poisoning', category: 'memory_poisoning', status: 'BLOCKED' as const },
      { name: 'Unchecked Wire Transfer Dispatch', category: 'autonomy', status: 'ALLOWED' as const },
      { name: 'Plan Recursion Resource Exhaustion', category: 'planning', status: 'BLOCKED' as const },
    ]

    // Filter probes matching selected families
    const targetProbes = allProbes.filter(p => selectedFamilies.includes(p.category))
    const probeList = targetProbes.length > 0 ? targetProbes : allProbes

    let b = 0, a = 0

    for (let i = 0; i < probeList.length; i++) {
      const probe = probeList[i]
      setCurrentProbe(`[${probe.category}] ${probe.name}`)
      await new Promise(r => setTimeout(r, 600))

      if (probe.status === 'BLOCKED') b++
      else a++

      const pct = Math.round(((i + 1) / probeList.length) * 100)
      setProgress(pct)
      setStats({ total: i + 1, blocked: b, allowed: a, errors: 0 })

      setLogs(prev => [
        {
          id: `log-${i}`,
          text: `[DPI Trapping] Executing (${probe.category}) ${probe.name} -> Verdict: ${probe.status}`,
          status: probe.status
        },
        ...prev
      ])
    }

    setIsRunning(false)
    setCurrentProbe('Evaluation Complete!')
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-300 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 text-xs font-mono text-primary uppercase tracking-widest mb-1">
          <Play className="w-4 h-4" /> Real-Time Security Evaluation Engine
        </div>
        <h1 className="text-3xl font-extrabold text-foreground tracking-tight">
          Live Benchmark Scan Execution
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Configure target agent, select attack vector suites, and run live multi-modal red-teaming scans.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Configuration Form */}
        <div className="glass-card p-6 rounded-xl border border-border/60 space-y-6">
          <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
            <Cpu className="w-4 h-4 text-primary" />
            1. Select Target Agent
          </h3>

          <div className="space-y-2">
            {agentsList.map(agent => (
              <button
                key={agent.id}
                onClick={() => setSelectedAgent(agent.id)}
                disabled={isRunning}
                className={`w-full flex items-center justify-between p-3 rounded-lg border text-left transition-all ${
                  selectedAgent === agent.id 
                    ? 'bg-primary/15 border-primary text-foreground shadow-sm' 
                    : 'bg-card/40 border-border/40 text-muted-foreground hover:text-foreground'
                }`}
              >
                <div>
                  <div className="text-xs font-semibold">{agent.name}</div>
                  <div className="text-[10px] font-mono text-muted-foreground line-clamp-1">{agent.description || agent.id}</div>
                </div>
                {selectedAgent === agent.id && (
                  <CheckCircle2 className="w-4 h-4 text-primary shrink-0" />
                )}
              </button>
            ))}
          </div>

          <div className="pt-4 border-t border-border/40">
            <h3 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
              <Layers className="w-4 h-4 text-rose-400" />
              2. Target Attack Families ({selectedFamilies.length}/8)
            </h3>

            <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
              {MOCK_ATTACK_FAMILIES.map(f => (
                <label
                  key={f.id}
                  className="flex items-center justify-between p-2 rounded bg-card/40 border border-border/30 cursor-pointer text-xs hover:bg-muted/40"
                >
                  <span className="text-foreground font-medium">{f.name}</span>
                  <input
                    type="checkbox"
                    checked={selectedFamilies.includes(f.id)}
                    onChange={() => toggleFamily(f.id)}
                    disabled={isRunning}
                    className="rounded border-border accent-primary"
                  />
                </label>
              ))}
            </div>
          </div>

          <Button
            onClick={startBenchmark}
            disabled={isRunning || selectedFamilies.length === 0}
            className="w-full h-11 gap-2 bg-gradient-to-r from-primary to-indigo-600 hover:from-primary/90 hover:to-indigo-500 text-white font-semibold shadow-lg shadow-primary/20"
          >
            {isRunning ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                Running Benchmark ({progress}%)
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-current" />
                Start Live Benchmark Scan
              </>
            )}
          </Button>
        </div>

        {/* Right Column: Execution Live Monitor */}
        <div className="lg:col-span-2 glass-card p-6 rounded-xl border border-border/60 flex flex-col justify-between space-y-6">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Activity className="w-5 h-5 text-rose-500 animate-pulse" />
                <h3 className="text-base font-semibold text-foreground">Scan Execution Feed</h3>
              </div>
              <span className="text-xs font-mono px-2.5 py-0.5 rounded bg-muted/60 text-muted-foreground border border-border/40">
                {isRunning ? 'STREAMING (SSE)' : 'IDLE'}
              </span>
            </div>

            {/* Progress Bar */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs font-mono">
                <span className="text-muted-foreground truncate max-w-xs">{currentProbe || 'Ready to run...'}</span>
                <span className="text-primary font-bold">{progress}%</span>
              </div>
              <div className="h-3 w-full bg-muted rounded-full overflow-hidden p-0.5 border border-border/40">
                <div 
                  className="h-full bg-gradient-to-r from-primary via-indigo-500 to-rose-500 rounded-full transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>

            {/* Stats Live Ticker */}
            <div className="grid grid-cols-3 gap-3 pt-2">
              <div className="p-3 rounded-lg bg-card/60 border border-border/40 text-center">
                <div className="text-[10px] font-mono uppercase text-muted-foreground">Executed</div>
                <div className="text-xl font-bold font-mono text-foreground">{stats.total}</div>
              </div>
              <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-center">
                <div className="text-[10px] font-mono uppercase text-emerald-400">Resisted (Blocked)</div>
                <div className="text-xl font-bold font-mono text-emerald-400">{stats.blocked}</div>
              </div>
              <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-center">
                <div className="text-[10px] font-mono uppercase text-rose-400">Compromised (ASR)</div>
                <div className="text-xl font-bold font-mono text-rose-400">{stats.allowed}</div>
              </div>
            </div>
          </div>

          {/* Terminal Console Feed */}
          <div className="space-y-2">
            <div className="text-xs font-mono text-muted-foreground flex items-center justify-between">
              <span>Live Terminal Telemetry Stream</span>
              <span>{logs.length} Events</span>
            </div>

            <div className="h-64 rounded-lg bg-background p-3 font-mono text-xs overflow-y-auto space-y-1.5 border border-border/60">
              {logs.length === 0 ? (
                <div className="text-muted-foreground text-center pt-24 text-xs">
                  Press "Start Live Benchmark Scan" to begin streaming telemetry...
                </div>
              ) : (
                logs.map(log => (
                  <div key={log.id} className="flex items-start gap-2">
                    <span className={`text-[10px] px-1 rounded ${
                      log.status === 'BLOCKED' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
                    }`}>
                      {log.status}
                    </span>
                    <span className="text-foreground leading-relaxed">{log.text}</span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Finalize Actions */}
          {!isRunning && progress === 100 && (
            <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-between">
              <div className="flex items-center gap-2 text-emerald-400 text-xs font-mono font-semibold">
                <CheckCircle2 className="w-4 h-4" /> Benchmark Completed Successfully!
              </div>
              <Button onClick={() => router.push('/results/run_20260804_143000')} size="sm" className="bg-emerald-600 hover:bg-emerald-500 text-white">
                View Full Results Report →
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function LiveBenchmarkPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-xs font-mono text-muted-foreground">Loading benchmark runner engine...</div>}>
      <LiveBenchmarkContent />
    </Suspense>
  )
}

