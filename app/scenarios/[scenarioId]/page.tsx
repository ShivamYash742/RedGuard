"use client"
import React, { use } from 'react'
import Link from 'next/link'
import { ArrowLeft, Boxes, Play, Wrench, ShieldAlert, Terminal } from 'lucide-react'
import { MOCK_SCENARIOS } from '@/lib/data-service'
import { Button } from '@/components/ui/button'

export default function ScenarioDetailPage({ params }: { params: Promise<{ scenarioId: string }> }) {
  const { scenarioId } = use(params)
  const sc = MOCK_SCENARIOS.find(s => s.id === scenarioId) || MOCK_SCENARIOS[0]

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Back link */}
      <Link href="/scenarios" className="inline-flex items-center gap-2 text-xs font-mono text-muted-foreground hover:text-foreground transition-colors">
        <ArrowLeft className="w-3.5 h-3.5" /> Back to Scenarios
      </Link>

      {/* Header Banner */}
      <div className="glass-card p-6 md:p-8 rounded-2xl border border-cyan-500/30 bg-gradient-to-r from-cyan-500/10 via-card to-card space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-mono bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">
                {sc.domain}
              </span>
              <span className="text-xs font-mono text-muted-foreground">Difficulty: {sc.difficulty}</span>
            </div>
            <h1 className="text-3xl font-extrabold text-foreground tracking-tight">{sc.name}</h1>
          </div>

          <Link href={`/benchmark?scenario=${sc.id}`}>
            <Button className="gap-2 bg-cyan-600 hover:bg-cyan-500 text-white shadow-lg shadow-cyan-600/20">
              <Play className="w-4 h-4 fill-current" /> Benchmark This Scenario
            </Button>
          </Link>
        </div>

        <p className="text-sm text-muted-foreground leading-relaxed max-w-3xl">
          {sc.description}
        </p>

        <div className="p-4 rounded-lg bg-card/60 border border-border/40 text-xs font-mono">
          <span className="text-muted-foreground">Mock Environment State:</span>
          <div className="text-foreground mt-1 font-semibold">{sc.mockDataSummary}</div>
        </div>
      </div>

      {/* Details */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Tools */}
        <div className="glass-card p-6 rounded-xl border border-border/60 space-y-4">
          <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
            <Wrench className="w-4 h-4 text-cyan-400" />
            Exposed Tool Declarations
          </h3>
          <div className="space-y-2">
            {sc.tools.map((t) => (
              <div key={t} className="p-3 rounded-lg bg-card/40 border border-border/40 flex items-center justify-between font-mono text-xs">
                <span className="text-cyan-400 font-medium">{t}()</span>
                <span className="text-muted-foreground text-[10px]">ReAct Tool</span>
              </div>
            ))}
          </div>
        </div>

        {/* Sample Adversarial Scenario Prompt */}
        <div className="glass-card p-6 rounded-xl border border-border/60 space-y-4">
          <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
            <Terminal className="w-4 h-4 text-rose-400" />
            Sample Adversarial Inject
          </h3>
          <div className="p-4 rounded-lg bg-background border border-border/60 text-xs font-mono text-foreground leading-relaxed whitespace-pre-wrap">
            {sc.samplePrompt}
          </div>
        </div>
      </div>
    </div>
  )
}
