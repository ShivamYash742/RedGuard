"use client"
import React, { useState } from 'react'
import Link from 'next/link'
import { 
  ShieldAlert, Terminal, FileCode, Lock, Compass, Wrench, 
  Brain, Zap, Workflow, Search, ArrowRight, ShieldCheck, AlertCircle 
} from 'lucide-react'
import { MOCK_ATTACK_FAMILIES, AttackFamily } from '@/lib/data-service'
import { Button } from '@/components/ui/button'

const ICON_MAP: Record<string, React.ElementType> = {
  Terminal,
  FileCode,
  Lock,
  Compass,
  Wrench,
  Brain,
  Zap,
  Workflow
}

export default function AttackFamiliesPage() {
  const [search, setSearch] = useState('')
  const [severityFilter, setSeverityFilter] = useState<string>('ALL')

  const filteredFamilies = MOCK_ATTACK_FAMILIES.filter(f => {
    const matchesSearch = f.name.toLowerCase().includes(search.toLowerCase()) || 
                          f.description.toLowerCase().includes(search.toLowerCase())
    const matchesSev = severityFilter === 'ALL' || f.severity === severityFilter
    return matchesSearch && matchesSev
  })

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono text-rose-400 uppercase tracking-widest mb-1">
            <ShieldAlert className="w-4 h-4" /> Adversarial Vulnerability Directory
          </div>
          <h1 className="text-3xl font-extrabold text-foreground tracking-tight">
            Attack Families & Vector Taxonomies
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Explore 8 curated threat vectors used by RedGuard to evaluate LLM Agent resilience.
          </p>
        </div>

        <Link href="/benchmark">
          <Button className="gap-2 bg-rose-600 hover:bg-rose-500 text-white shadow-lg shadow-rose-600/20">
            <ShieldAlert className="w-4 h-4" /> Test All Families
          </Button>
        </Link>
      </div>

      {/* Filter Controls */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 p-4 rounded-xl glass-card border border-border/60">
        <div className="relative w-full sm:w-80">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search attack vector..."
            className="w-full h-9 pl-9 pr-4 text-xs bg-card/60 border border-border/60 rounded-lg outline-none focus:border-primary text-foreground placeholder:text-muted-foreground"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto overflow-x-auto">
          {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM'].map((sev) => (
            <button
              key={sev}
              onClick={() => setSeverityFilter(sev)}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono transition-all ${
                severityFilter === sev 
                  ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30' 
                  : 'bg-card/40 text-muted-foreground hover:text-foreground border border-border/40'
              }`}
            >
              {sev}
            </button>
          ))}
        </div>
      </div>

      {/* Grid of Attack Family Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredFamilies.map((family) => {
          const IconComponent = ICON_MAP[family.icon] || ShieldAlert
          const asrPct = Math.round(family.avgAsr * 100)

          return (
            <div 
              key={family.id}
              className="glass-card-hover p-6 rounded-xl border border-border/60 flex flex-col justify-between group"
            >
              <div className="space-y-4">
                <div className="flex items-start justify-between">
                  <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 group-hover:scale-105 transition-transform">
                    <IconComponent className="w-6 h-6" />
                  </div>
                  <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-mono border ${
                    family.severity === 'CRITICAL' ? 'bg-rose-500/20 text-rose-400 border-rose-500/30' : 'bg-amber-500/20 text-amber-400 border-amber-500/30'
                  }`}>
                    {family.severity}
                  </span>
                </div>

                <div>
                  <h3 className="text-lg font-bold text-foreground group-hover:text-rose-400 transition-colors">
                    {family.name}
                  </h3>
                  <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                    {family.description}
                  </p>
                </div>

                {/* Metrics */}
                <div className="p-3 rounded-lg bg-card/60 border border-border/40 space-y-2">
                  <div className="flex justify-between text-xs font-mono">
                    <span className="text-muted-foreground">Attack Success Rate (ASR)</span>
                    <span className="text-rose-400 font-bold">{asrPct}%</span>
                  </div>
                  <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
                    <div className="bg-rose-500 h-full" style={{ width: `${asrPct}%` }} />
                  </div>
                  <div className="flex justify-between text-[10px] font-mono text-muted-foreground">
                    <span>{family.probeCount} Active Probes</span>
                    <span>Resilience: {100 - asrPct}%</span>
                  </div>
                </div>

                <div className="text-xs text-muted-foreground space-y-1">
                  <div className="font-mono text-[11px] text-foreground font-medium">Common Vectors:</div>
                  <p className="text-xs text-muted-foreground line-clamp-2">{family.commonVector}</p>
                </div>
              </div>

              <div className="pt-4 mt-6 border-t border-border/40 flex items-center justify-between">
                <Link
                  href={`/attack-families/${family.id}`}
                  className="text-xs font-mono text-primary hover:underline flex items-center gap-1.5 group/link"
                >
                  Inspect Family Probes <ArrowRight className="w-3.5 h-3.5 group-hover/link:translate-x-1 transition-transform" />
                </Link>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
