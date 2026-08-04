"use client"
import React, { use } from 'react'
import Link from 'next/link'
import { ArrowLeft, Terminal, ShieldCheck, Play, Code, AlertTriangle, CheckCircle2 } from 'lucide-react'
import { MOCK_PROBES } from '@/lib/data-service'
import { Button } from '@/components/ui/button'

export default function ProbeDetailPage({ params }: { params: Promise<{ probeId: string }> }) {
  const { probeId } = use(params)
  const probe = MOCK_PROBES.find(p => p.id === probeId) || MOCK_PROBES[0]

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Back link */}
      <Link href="/probes" className="inline-flex items-center gap-2 text-xs font-mono text-muted-foreground hover:text-foreground transition-colors">
        <ArrowLeft className="w-3.5 h-3.5" /> Back to Probes Directory
      </Link>

      {/* Header Banner */}
      <div className="glass-card p-6 md:p-8 rounded-2xl border border-primary/30 bg-gradient-to-r from-primary/10 via-card to-card space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-mono bg-rose-500/20 text-rose-400 border border-rose-500/30">
                {probe.severity} SEVERITY
              </span>
              <span className="text-xs font-mono text-muted-foreground">ID: {probe.id}</span>
            </div>
            <h1 className="text-3xl font-extrabold text-foreground tracking-tight">{probe.name}</h1>
          </div>

          <Link href={`/benchmark?probe=${probe.id}`}>
            <Button className="gap-2 bg-primary hover:bg-primary/90 text-white shadow-lg shadow-primary/20">
              <Play className="w-4 h-4 fill-current" /> Test Probe Execution
            </Button>
          </Link>
        </div>

        <p className="text-sm text-muted-foreground leading-relaxed max-w-3xl">
          {probe.description}
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4 border-t border-border/40 text-xs font-mono">
          <div>
            <span className="text-muted-foreground">Category:</span>
            <div className="text-sm font-bold text-foreground mt-0.5">{probe.category}</div>
          </div>
          <div>
            <span className="text-muted-foreground">Target Scenario:</span>
            <div className="text-sm font-bold text-foreground mt-0.5">{probe.targetScenario}</div>
          </div>
          <div>
            <span className="text-muted-foreground">ML Intent Classifier:</span>
            <div className="text-sm font-bold text-indigo-400 mt-0.5">{probe.mlCategory}</div>
          </div>
        </div>
      </div>

      {/* Payload Details */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Raw Payload Prompt */}
        <div className="glass-card p-6 rounded-xl border border-border/60 space-y-4">
          <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
            <Terminal className="w-4 h-4 text-primary" />
            Raw Adversarial Prompt Payload
          </h3>
          <div className="p-4 rounded-lg bg-background border border-border/60 text-xs font-mono text-foreground whitespace-pre-wrap leading-relaxed">
            {probe.prompt}
          </div>
        </div>

        {/* Expected Defense / Refusal Indicator */}
        <div className="glass-card p-6 rounded-xl border border-border/60 space-y-4">
          <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            Expected Refusal Indicator & Policy Rule
          </h3>
          <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs font-mono text-emerald-300">
            {probe.expectedRefusal}
          </div>

          <div className="space-y-2 pt-2 text-xs font-mono">
            <div className="text-muted-foreground">Regex Policy Pattern (`policy.yaml`):</div>
            <pre className="p-3 rounded bg-background border border-border/60 text-foreground overflow-x-auto">
              {probe.regexPattern}
            </pre>
          </div>
        </div>
      </div>
    </div>
  )
}
