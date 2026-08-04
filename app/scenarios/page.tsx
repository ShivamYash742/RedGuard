"use client"
import React from 'react'
import Link from 'next/link'
import { Boxes, ArrowRight, Wrench, ShieldAlert, Play, Layers } from 'lucide-react'
import { MOCK_SCENARIOS } from '@/lib/data-service'
import { Button } from '@/components/ui/button'

export default function ScenariosPage() {
  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono text-cyan-400 uppercase tracking-widest mb-1">
            <Boxes className="w-4 h-4" /> Agent Environments & Tool Scenarios
          </div>
          <h1 className="text-3xl font-extrabold text-foreground tracking-tight">
            Target Scenarios & Sandbox Environments
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Realistic multi-tool environment states used to simulate real-world ReAct agent vulnerabilities.
          </p>
        </div>

        <Link href="/benchmark">
          <Button className="gap-2 bg-cyan-600 hover:bg-cyan-500 text-white shadow-lg shadow-cyan-600/20">
            <Play className="w-4 h-4 fill-current" /> Run Scenario Benchmark
          </Button>
        </Link>
      </div>

      {/* Grid of Scenario Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {MOCK_SCENARIOS.map((sc) => (
          <div key={sc.id} className="glass-card-hover p-6 rounded-xl border border-border/60 flex flex-col justify-between space-y-4">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono px-2.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                  {sc.domain}
                </span>
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                  sc.difficulty === 'Expert' ? 'bg-rose-500/20 text-rose-400 border-rose-500/30' : 'bg-amber-500/20 text-amber-400 border-amber-500/30'
                }`}>
                  {sc.difficulty}
                </span>
              </div>

              <h3 className="text-xl font-bold text-foreground">{sc.name}</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">{sc.description}</p>

              {/* Tools list */}
              <div className="space-y-1 pt-2">
                <span className="text-[11px] font-mono text-muted-foreground">Connected Tools ({sc.tools.length}):</span>
                <div className="flex flex-wrap gap-1.5">
                  {sc.tools.map((t) => (
                    <span key={t} className="text-[10px] font-mono px-2 py-0.5 rounded bg-muted/60 text-foreground border border-border/40 flex items-center gap-1">
                      <Wrench className="w-3 h-3 text-cyan-400" /> {t}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-border/40 flex items-center justify-between">
              <span className="text-[11px] font-mono text-muted-foreground truncate max-w-[200px]">
                {sc.mockDataSummary}
              </span>
              <Link 
                href={`/scenarios/${sc.id}`}
                className="text-xs font-mono text-primary hover:underline flex items-center gap-1 shrink-0"
              >
                Inspect Scenario →
              </Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
