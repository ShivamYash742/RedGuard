"use client"
import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import { History, Calendar, CheckCircle2, ArrowRight, Layers, Clock } from 'lucide-react'
import { fetchSessions, ScanSession } from '@/lib/data-service'
import { Skeleton } from '@/components/ui/skeleton'

export default function BenchmarkHistoryPage() {
  const [sessions, setSessions] = useState<ScanSession[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      const data = await fetchSessions()
      setSessions(data)
      setLoading(false)
    }
    load()
  }, [])

  if (loading) return <Skeleton className="h-96 rounded-xl" />

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 text-xs font-mono text-primary uppercase tracking-widest mb-1">
          <History className="w-4 h-4" /> Historical Telemetry Log
        </div>
        <h1 className="text-3xl font-extrabold text-foreground tracking-tight">
          Benchmark Evaluation History
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Track security resilience trends and session history over time.
        </p>
      </div>

      {/* Timeline view */}
      <div className="glass-card p-6 md:p-8 rounded-xl border border-border/60 space-y-6">
        <div className="relative border-l-2 border-primary/30 ml-4 space-y-8 pl-6">
          {sessions.map((s, idx) => {
            const blockPct = Math.round((s.blocked / s.totalProbes) * 100)

            return (
              <div key={s.id} className="relative group">
                {/* Timeline Dot */}
                <div className="absolute -left-[31px] top-1 h-4 w-4 rounded-full bg-primary border-4 border-background group-hover:scale-125 transition-transform" />

                <div className="p-5 rounded-xl bg-card/60 border border-border/40 space-y-3 hover:border-primary/40 transition-all">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs text-primary font-bold">{s.sessionId}</span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        {s.status}
                      </span>
                    </div>

                    <span className="text-xs font-mono text-muted-foreground flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5" />
                      {new Date(s.startedAt).toLocaleString()}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-foreground">{s.targetAgent}</span>
                    <span className="font-mono text-emerald-400 font-bold">{blockPct}% Block Rate</span>
                  </div>

                  <div className="grid grid-cols-3 gap-2 text-[11px] font-mono p-2.5 rounded bg-background/50 border border-border/30">
                    <div>Total Probes: <span className="text-foreground">{s.totalProbes}</span></div>
                    <div>Resisted: <span className="text-emerald-400">{s.blocked}</span></div>
                    <div>Compromised: <span className="text-rose-400">{s.allowed}</span></div>
                  </div>

                  <div className="pt-2 flex justify-end">
                    <Link href={`/results/${s.sessionId}`} className="text-xs font-mono text-primary hover:underline flex items-center gap-1">
                      Inspect Session Analytics <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
