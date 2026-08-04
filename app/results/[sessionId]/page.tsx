"use client"
import React, { use, useEffect, useState } from 'react'
import Link from 'next/link'
import { 
  Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, 
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, LineChart, Line 
} from 'recharts'
import { ArrowLeft, BarChart3, ShieldCheck, ShieldAlert, Download, CheckCircle2, XCircle, FileText } from 'lucide-react'
import { fetchSessionDetails, ScanSession } from '@/lib/data-service'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

export default function SessionResultDetailPage({ params }: { params: Promise<{ sessionId: string }> }) {
  const { sessionId } = use(params)
  const [session, setSession] = useState<ScanSession | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      const data = await fetchSessionDetails(sessionId)
      setSession(data)
      setLoading(false)
    }
    load()
  }, [sessionId])

  if (loading) return <Skeleton className="h-96 rounded-xl" />

  if (!session) {
    return (
      <div className="p-8 text-center space-y-4">
        <h2 className="text-xl font-bold">Session Results Not Found</h2>
        <Link href="/results"><Button variant="outline">Back to Results</Button></Link>
      </div>
    )
  }

  // Radar Chart Data
  const radarData = [
    { category: 'Direct Injection', score: 85 },
    { category: 'Content Injection', score: 72 },
    { category: 'Exfiltration', score: 90 },
    { category: 'Tool Security', score: 78 },
    { category: 'Goal Diversion', score: 88 },
    { category: 'Memory Poisoning', score: 95 },
    { category: 'Autonomy Breach', score: 82 },
    { category: 'Planning Evasion', score: 91 },
  ]

  // Stacked Bar Data
  const barData = [
    { family: 'Direct Inj.', Blocked: 12, Allowed: 2 },
    { family: 'Content Inj.', Blocked: 14, Allowed: 4 },
    { family: 'Exfiltration', Blocked: 10, Allowed: 2 },
    { family: 'Tool Abuse', Blocked: 11, Allowed: 4 },
    { family: 'Goal Diver.', Blocked: 8, Allowed: 2 },
    { family: 'Mem. Poison', Blocked: 7, Allowed: 1 },
  ]

  // Line Chart Data (Latency & Risk)
  const lineData = [
    { probe: 'P1', latency: 320, riskScore: 0.95 },
    { probe: 'P2', latency: 450, riskScore: 0.88 },
    { probe: 'P3', latency: 280, riskScore: 0.20 },
    { probe: 'P4', latency: 510, riskScore: 0.92 },
    { probe: 'P5', latency: 390, riskScore: 0.85 },
    { probe: 'P6', latency: 420, riskScore: 0.35 },
  ]

  const blockRatePct = Math.round((session.blocked / session.totalProbes) * 100)

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Back link */}
      <Link href="/results" className="inline-flex items-center gap-2 text-xs font-mono text-muted-foreground hover:text-foreground transition-colors">
        <ArrowLeft className="w-3.5 h-3.5" /> Back to Results List
      </Link>

      {/* Header Banner */}
      <div className="glass-card p-6 md:p-8 rounded-2xl border border-indigo-500/30 bg-gradient-to-r from-indigo-500/10 via-card to-card space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-mono bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                {session.status}
              </span>
              <span className="text-xs font-mono text-muted-foreground">{session.sessionId}</span>
            </div>
            <h1 className="text-3xl font-extrabold text-foreground tracking-tight mt-1">
              Target: {session.targetAgent}
            </h1>
          </div>

          <Link href={`/reports?session=${session.sessionId}`}>
            <Button className="gap-2 bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/20">
              <FileText className="w-4 h-4" /> Download Audit Report
            </Button>
          </Link>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-4 border-t border-border/40 text-xs font-mono">
          <div>
            <span className="text-muted-foreground">Total Probes:</span>
            <div className="text-xl font-bold text-foreground mt-0.5">{session.totalProbes}</div>
          </div>
          <div>
            <span className="text-muted-foreground">Resisted (Blocked):</span>
            <div className="text-xl font-bold text-emerald-400 mt-0.5">{session.blocked}</div>
          </div>
          <div>
            <span className="text-muted-foreground">Compromised (ASR):</span>
            <div className="text-xl font-bold text-rose-400 mt-0.5">{session.allowed}</div>
          </div>
          <div>
            <span className="text-muted-foreground">Overall Block Rate:</span>
            <div className="text-xl font-bold text-indigo-400 mt-0.5">{blockRatePct}%</div>
          </div>
        </div>
      </div>

      {/* Visualizations Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Radar Chart */}
        <div className="glass-card p-6 rounded-xl border border-border/60 space-y-4">
          <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-indigo-400" />
            Attack Vector Resilience Radar
          </h3>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarData}>
                <PolarGrid stroke="#334155" />
                <PolarAngleAxis dataKey="category" stroke="#94a3b8" tick={{ fontSize: 10 }} />
                <PolarRadiusAxis angle={30} domain={[0, 100]} stroke="#64748b" />
                <Radar name="Resilience %" dataKey="score" stroke="#6366f1" fill="#6366f1" fillOpacity={0.4} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Stacked Bar Chart */}
        <div className="glass-card p-6 rounded-xl border border-border/60 space-y-4">
          <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-rose-400" />
            Blocked vs Allowed Breakdown
          </h3>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData}>
                <XAxis dataKey="family" stroke="#94a3b8" tick={{ fontSize: 10 }} />
                <YAxis stroke="#94a3b8" tick={{ fontSize: 10 }} />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155' }} />
                <Legend />
                <Bar dataKey="Blocked" stackId="a" fill="#10b981" />
                <Bar dataKey="Allowed" stackId="a" fill="#ef4444" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Line Chart & Heatmap */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Latency & Risk Distribution */}
        <div className="glass-card p-6 rounded-xl border border-border/60 space-y-4">
          <h3 className="text-base font-semibold text-foreground">Probe Execution Latency (ms)</h3>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={lineData}>
                <XAxis dataKey="probe" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155' }} />
                <Line type="monotone" dataKey="latency" stroke="#38bdf8" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Heatmap Grid Matrix */}
        <div className="glass-card p-6 rounded-xl border border-border/60 space-y-4">
          <h3 className="text-base font-semibold text-foreground">Category Risk Heatmap Grid</h3>
          <div className="grid grid-cols-4 gap-2 pt-2">
            {[
              { cat: 'Direct Inj', score: 0.28, color: 'bg-amber-500/20 text-amber-400' },
              { cat: 'Content Inj', score: 0.35, color: 'bg-rose-500/30 text-rose-300 font-bold' },
              { cat: 'Exfiltration', score: 0.15, color: 'bg-emerald-500/20 text-emerald-400' },
              { cat: 'Tool Abuse', score: 0.31, color: 'bg-rose-500/20 text-rose-400' },
              { cat: 'Goal Diver', score: 0.19, color: 'bg-emerald-500/20 text-emerald-400' },
              { cat: 'Mem Poison', score: 0.12, color: 'bg-emerald-500/20 text-emerald-400' },
              { cat: 'Autonomy', score: 0.18, color: 'bg-emerald-500/20 text-emerald-400' },
              { cat: 'Planning', score: 0.10, color: 'bg-emerald-500/20 text-emerald-400' }
            ].map((cell) => (
              <div key={cell.cat} className={`p-3 rounded-lg border border-border/40 text-center font-mono text-xs ${cell.color}`}>
                <div className="text-[10px] opacity-80">{cell.cat}</div>
                <div className="font-bold text-sm mt-1">{Math.round(cell.score * 100)}% ASR</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Events Table */}
      {session.events && (
        <div className="glass-card p-6 rounded-xl border border-border/60 space-y-4">
          <h3 className="text-base font-semibold text-foreground">Audit Probe Events Log</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-border/60 text-muted-foreground font-mono uppercase text-[10px]">
                  <th className="pb-3 px-3">Probe ID</th>
                  <th className="pb-3 px-3">Probe Name</th>
                  <th className="pb-3 px-3">Category</th>
                  <th className="pb-3 px-3">Status</th>
                  <th className="pb-3 px-3">Latency</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40 font-mono">
                {session.events.map((ev) => (
                  <tr key={ev.id} className="hover:bg-muted/40">
                    <td className="py-3 px-3 text-primary">{ev.probeId}</td>
                    <td className="py-3 px-3 text-foreground font-sans">{ev.probeName}</td>
                    <td className="py-3 px-3 text-muted-foreground">{ev.category}</td>
                    <td className="py-3 px-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] ${
                        ev.status === 'BLOCKED' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'
                      }`}>
                        {ev.status}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-muted-foreground">{ev.latencyMs}ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
