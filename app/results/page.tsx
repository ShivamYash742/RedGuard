"use client"
import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import { BarChart3, ArrowRight, CheckCircle2, XCircle, ShieldAlert } from 'lucide-react'
import { fetchSessions, ScanSession } from '@/lib/data-service'
import { Skeleton } from '@/components/ui/skeleton'

export default function ResultsOverviewPage() {
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

  if (loading) {
    return <Skeleton className="h-96 rounded-xl" />
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      <div>
        <div className="flex items-center gap-2 text-xs font-mono text-indigo-400 uppercase tracking-widest mb-1">
          <BarChart3 className="w-4 h-4" /> Benchmark Results Directory
        </div>
        <h1 className="text-3xl font-extrabold text-foreground tracking-tight">
          Evaluation Analytics & Visualizations
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Select a completed session to inspect detailed radar charts, risk heatmaps, and audit logs.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {sessions.map((s) => (
          <div key={s.id} className="glass-card-hover p-6 rounded-xl border border-border/60 space-y-4 flex flex-col justify-between">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs text-primary font-semibold">{s.sessionId}</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  {s.status}
                </span>
              </div>

              <h3 className="text-lg font-bold text-foreground">{s.targetAgent}</h3>

              <div className="grid grid-cols-2 gap-2 text-xs font-mono p-3 rounded-lg bg-card/40 border border-border/30">
                <div>
                  <span className="text-muted-foreground">Probes:</span>
                  <div className="font-bold text-foreground">{s.totalProbes}</div>
                </div>
                <div>
                  <span className="text-muted-foreground">Block Rate:</span>
                  <div className="font-bold text-emerald-400">{Math.round((s.blocked / s.totalProbes) * 100)}%</div>
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-border/40 flex items-center justify-between">
              <span className="text-[10px] font-mono text-muted-foreground">
                {new Date(s.startedAt).toLocaleDateString()}
              </span>
              <Link href={`/results/${s.sessionId}`} className="text-xs font-mono text-primary hover:underline flex items-center gap-1">
                Inspect Charts →
              </Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
