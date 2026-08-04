"use client"
import React, { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { 
  Search, ShieldAlert, Terminal, Boxes, PlayCircle, BarChart3, 
  FileText, Database, X, ArrowRight 
} from 'lucide-react'
import { MOCK_ATTACK_FAMILIES, MOCK_PROBES, MOCK_SCENARIOS, MOCK_SESSIONS, MOCK_LEADERBOARD } from '@/lib/data-service'

interface GlobalSearchProps {
  isOpen: boolean
  onClose: () => void
}

export function GlobalSearch({ isOpen, onClose }: GlobalSearchProps) {
  const router = useRouter()
  const [query, setQuery] = useState('')

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        if (isOpen) onClose()
        else setQuery('')
      }
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  const q = query.toLowerCase().trim()

  const matchedFamilies = MOCK_ATTACK_FAMILIES.filter(
    f => f.name.toLowerCase().includes(q) || f.description.toLowerCase().includes(q)
  )

  const matchedProbes = MOCK_PROBES.filter(
    p => p.name.toLowerCase().includes(q) || p.prompt.toLowerCase().includes(q) || p.category.toLowerCase().includes(q)
  )

  const matchedScenarios = MOCK_SCENARIOS.filter(
    s => s.name.toLowerCase().includes(q) || s.domain.toLowerCase().includes(q)
  )

  const matchedSessions = MOCK_SESSIONS.filter(
    s => s.sessionId.toLowerCase().includes(q) || s.targetAgent.toLowerCase().includes(q)
  )

  const matchedModels = MOCK_LEADERBOARD.filter(
    m => m.modelName.toLowerCase().includes(q) || m.provider.toLowerCase().includes(q)
  )

  const handleNavigate = (path: string) => {
    router.push(path)
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 bg-background/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl bg-card border border-border rounded-xl shadow-2xl overflow-hidden glass-card">
        {/* Input header */}
        <div className="flex items-center px-4 border-b border-border/60">
          <Search className="w-5 h-5 text-muted-foreground mr-3" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search probes, attack families, scenarios, benchmark runs, models... (Cmd+K)"
            className="w-full h-14 bg-transparent text-foreground placeholder:text-muted-foreground outline-none text-base font-sans"
            autoFocus
          />
          <button 
            onClick={onClose}
            className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Results Body */}
        <div className="max-h-[60vh] overflow-y-auto p-4 space-y-6">
          {q === '' && (
            <div className="text-xs text-muted-foreground uppercase tracking-wider font-mono">
              Quick Nav Suggestions
            </div>
          )}

          {/* Quick Nav Items */}
          {q === '' && (
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => handleNavigate('/benchmark')}
                className="flex items-center gap-3 p-3 rounded-lg border border-border/40 hover:bg-muted/50 text-left transition-all group"
              >
                <PlayCircle className="w-5 h-5 text-primary" />
                <div>
                  <div className="text-sm font-medium text-foreground group-hover:text-primary transition-colors">Live Benchmark</div>
                  <div className="text-xs text-muted-foreground">Run vulnerability scanner</div>
                </div>
              </button>
              <button
                onClick={() => handleNavigate('/attack-families')}
                className="flex items-center gap-3 p-3 rounded-lg border border-border/40 hover:bg-muted/50 text-left transition-all group"
              >
                <ShieldAlert className="w-5 h-5 text-rose-500" />
                <div>
                  <div className="text-sm font-medium text-foreground group-hover:text-rose-400 transition-colors">Attack Families</div>
                  <div className="text-xs text-muted-foreground">Browse 8 probe vectors</div>
                </div>
              </button>
              <button
                onClick={() => handleNavigate('/comparison')}
                className="flex items-center gap-3 p-3 rounded-lg border border-border/40 hover:bg-muted/50 text-left transition-all group"
              >
                <BarChart3 className="w-5 h-5 text-indigo-400" />
                <div>
                  <div className="text-sm font-medium text-foreground group-hover:text-indigo-300 transition-colors">Model Comparison</div>
                  <div className="text-xs text-muted-foreground">Leaderboard & metrics</div>
                </div>
              </button>
              <button
                onClick={() => handleNavigate('/datasets')}
                className="flex items-center gap-3 p-3 rounded-lg border border-border/40 hover:bg-muted/50 text-left transition-all group"
              >
                <Database className="w-5 h-5 text-emerald-400" />
                <div>
                  <div className="text-sm font-medium text-foreground group-hover:text-emerald-300 transition-colors">Dataset Explorer</div>
                  <div className="text-xs text-muted-foreground">Coverage statistics</div>
                </div>
              </button>
            </div>
          )}

          {/* Attack Families */}
          {matchedFamilies.length > 0 && (
            <div>
              <div className="text-xs font-mono text-muted-foreground mb-2 flex items-center gap-1.5">
                <ShieldAlert className="w-3.5 h-3.5 text-rose-500" /> Attack Families
              </div>
              <div className="space-y-1">
                {matchedFamilies.slice(0, 3).map(f => (
                  <button
                    key={f.id}
                    onClick={() => handleNavigate(`/attack-families/${f.id}`)}
                    className="w-full flex items-center justify-between p-2.5 rounded-lg hover:bg-muted/60 text-left transition-colors group"
                  >
                    <div>
                      <span className="text-sm font-medium text-foreground group-hover:text-primary">{f.name}</span>
                      <p className="text-xs text-muted-foreground line-clamp-1">{f.description}</p>
                    </div>
                    <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-primary group-hover:translate-x-1 transition-all" />
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Probes */}
          {matchedProbes.length > 0 && (
            <div>
              <div className="text-xs font-mono text-muted-foreground mb-2 flex items-center gap-1.5">
                <Terminal className="w-3.5 h-3.5 text-primary" /> Probes
              </div>
              <div className="space-y-1">
                {matchedProbes.slice(0, 3).map(p => (
                  <button
                    key={p.id}
                    onClick={() => handleNavigate(`/probes/${p.id}`)}
                    className="w-full flex items-center justify-between p-2.5 rounded-lg hover:bg-muted/60 text-left transition-colors group"
                  >
                    <div>
                      <span className="text-sm font-medium text-foreground group-hover:text-primary">{p.name}</span>
                      <p className="text-xs text-muted-foreground font-mono line-clamp-1">{p.prompt}</p>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20">
                      {p.severity}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Scenarios */}
          {matchedScenarios.length > 0 && (
            <div>
              <div className="text-xs font-mono text-muted-foreground mb-2 flex items-center gap-1.5">
                <Boxes className="w-3.5 h-3.5 text-cyan-400" /> Scenarios
              </div>
              <div className="space-y-1">
                {matchedScenarios.slice(0, 3).map(s => (
                  <button
                    key={s.id}
                    onClick={() => handleNavigate(`/scenarios/${s.id}`)}
                    className="w-full flex items-center justify-between p-2.5 rounded-lg hover:bg-muted/60 text-left transition-colors group"
                  >
                    <div>
                      <span className="text-sm font-medium text-foreground group-hover:text-primary">{s.name}</span>
                      <p className="text-xs text-muted-foreground">{s.domain} • {s.tools.length} tools</p>
                    </div>
                    <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-primary group-hover:translate-x-1 transition-all" />
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Sessions */}
          {matchedSessions.length > 0 && (
            <div>
              <div className="text-xs font-mono text-muted-foreground mb-2 flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-indigo-400" /> Benchmark Runs
              </div>
              <div className="space-y-1">
                {matchedSessions.slice(0, 3).map(s => (
                  <button
                    key={s.id}
                    onClick={() => handleNavigate(`/results/${s.sessionId}`)}
                    className="w-full flex items-center justify-between p-2.5 rounded-lg hover:bg-muted/60 text-left transition-colors group"
                  >
                    <div>
                      <span className="text-sm font-mono text-foreground group-hover:text-primary">{s.sessionId}</span>
                      <p className="text-xs text-muted-foreground">{s.targetAgent} • {s.blocked}/{s.totalProbes} Resisted</p>
                    </div>
                    <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-primary group-hover:translate-x-1 transition-all" />
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="p-3 bg-muted/40 border-t border-border/60 flex items-center justify-between text-xs text-muted-foreground font-mono">
          <span>Press <kbd className="px-1.5 py-0.5 rounded bg-muted text-foreground">ESC</kbd> to close</span>
          <span>RedGuard Search v1.0</span>
        </div>
      </div>
    </div>
  )
}
