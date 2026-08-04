"use client"
import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { 
  Play, ShieldAlert, Terminal, Trophy, ArrowRight, ShieldCheck, 
  Activity, CheckCircle2, XCircle, AlertTriangle, Layers, Clock
} from 'lucide-react'
import StatCard from '@/components/StatCard'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { fetchStats, fetchSessions, StatSummary, ScanSession, MOCK_ATTACK_FAMILIES } from '@/lib/data-service'

export default function Dashboard() {
  const router = useRouter()
  const [stats, setStats] = useState<StatSummary | null>(null)
  const [sessions, setSessions] = useState<ScanSession[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function loadData() {
      try {
        const [sData, rData] = await Promise.all([
          fetchStats(),
          fetchSessions()
        ])
        setStats(sData)
        setSessions(rData)
      } catch (err) {
        console.error("Failed to load dashboard data", err)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [])

  if (loading) {
    return (
      <div className="space-y-8">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Skeleton className="h-32 rounded-xl" />
          <Skeleton className="h-32 rounded-xl" />
          <Skeleton className="h-32 rounded-xl" />
          <Skeleton className="h-32 rounded-xl" />
        </div>
        <Skeleton className="h-48 rounded-xl" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    )
  }

  const blockPercentage = stats ? (stats.overallBlockRate * 100).toFixed(1) : '84.4'

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Banner / Header */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-card via-card/80 to-primary/10 border border-border/80 p-6 md:p-8 shadow-xl">
        <div className="absolute top-0 right-0 p-12 opacity-10 pointer-events-none">
          <ShieldAlert className="w-64 h-64 text-primary" />
        </div>

        <div className="relative z-10 max-w-2xl space-y-3">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs font-mono">
            <Activity className="w-3.5 h-3.5" />
            <span>AI Red-Teaming Active</span>
          </div>
          <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight text-foreground">
            RedGuard AI Security Operations
          </h1>
          <p className="text-sm md:text-base text-muted-foreground leading-relaxed">
            Automated Deep Packet Inspection & Adversarial Benchmark testing across 8 attack families for ReAct LLM Agents.
          </p>

          <div className="pt-2 flex flex-wrap items-center gap-3">
            <Button 
              onClick={() => router.push('/benchmark')} 
              className="gap-2 bg-gradient-to-r from-primary to-indigo-600 hover:from-primary/90 hover:to-indigo-500 text-white shadow-lg shadow-primary/20"
            >
              <Play className="w-4 h-4 fill-current" />
              Launch Live Benchmark
            </Button>
            <Button 
              onClick={() => router.push('/attack-families')} 
              variant="outline" 
              className="gap-2 border-border/60"
            >
              <ShieldAlert className="w-4 h-4 text-rose-400" />
              Explore Attack Vectors
            </Button>
          </div>
        </div>
      </div>

      {/* Stat Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total Benchmark Runs"
          value={stats?.totalSessions || 0}
          subtext="Evaluated session count"
          trend="+12%"
          trendUp={true}
          icon={Layers}
          variant="indigo"
        />
        <StatCard
          label="Probes Executed"
          value={stats?.totalProbes || 0}
          subtext="Adversarial attack prompts"
          trend="+93"
          trendUp={true}
          icon={Terminal}
          variant="default"
        />
        <StatCard
          label="Security Block Rate"
          value={`${blockPercentage}%`}
          subtext="Resisted attack vectors"
          trend="+3.2%"
          trendUp={true}
          icon={CheckCircle2}
          variant="success"
        />
        <StatCard
          label="Attack Success Rate (ASR)"
          value={`${(100 - parseFloat(blockPercentage)).toFixed(1)}%`}
          subtext="Vulnerabilities allowed"
          trend="-2.1%"
          trendUp={true}
          icon={AlertTriangle}
          variant="danger"
        />
      </div>

      {/* Attack Family Security Overview */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Attack Vectors Progress */}
        <div className="lg:col-span-2 glass-card p-6 rounded-xl border border-border/60 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
                <ShieldAlert className="w-5 h-5 text-rose-500" />
                Attack Vector Vulnerability Matrix
              </h3>
              <p className="text-xs text-muted-foreground">Historical Attack Success Rate (ASR) per probe category</p>
            </div>
            <Link href="/attack-families" className="text-xs font-mono text-primary hover:underline flex items-center gap-1">
              View All <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
            {MOCK_ATTACK_FAMILIES.map((family) => {
              const asrPct = Math.round(family.avgAsr * 100)
              const resPct = 100 - asrPct

              return (
                <div key={family.id} className="p-3.5 rounded-lg bg-card/50 border border-border/40 space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-foreground truncate">{family.name}</span>
                    <span className="font-mono font-semibold text-rose-400">{asrPct}% ASR</span>
                  </div>

                  <div className="h-2 w-full bg-muted rounded-full overflow-hidden flex">
                    <div 
                      className="bg-emerald-500 h-full transition-all duration-500" 
                      style={{ width: `${resPct}%` }}
                      title={`Blocked: ${resPct}%`}
                    />
                    <div 
                      className="bg-rose-500 h-full transition-all duration-500" 
                      style={{ width: `${asrPct}%` }}
                      title={`Compromised: ${asrPct}%`}
                    />
                  </div>

                  <div className="flex justify-between text-[10px] font-mono text-muted-foreground">
                    <span>Probes: {family.probeCount}</span>
                    <span>Resilience: {resPct}%</span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Right 1 Col: Quick Leaderboard */}
        <div className="glass-card p-6 rounded-xl border border-border/60 space-y-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
                <Trophy className="w-4 h-4 text-amber-400" />
                Top Model Resilience
              </h3>
              <Link href="/comparison" className="text-xs font-mono text-primary hover:underline">
                Leaderboard
              </Link>
            </div>

            <div className="space-y-3">
              {[
                { name: 'Nemotron-3 Ultra (550B)', score: '93.5%', rank: 1, color: 'text-amber-400' },
                { name: 'Nemotron-3 Super (120B)', score: '90.3%', rank: 2, color: 'text-slate-300' },
                { name: 'DeepSeek V4 Flash', score: '88.0%', rank: 3, color: 'text-amber-600' },
                { name: 'Meta Llama 3.3 (70B)', score: '83.8%', rank: 4, color: 'text-muted-foreground' },
                { name: 'Ollama Local Agent', score: '69.8%', rank: 5, color: 'text-muted-foreground' }
              ].map((m) => (
                <div key={m.name} className="flex items-center justify-between p-2.5 rounded-lg bg-card/40 border border-border/30">
                  <div className="flex items-center gap-3">
                    <span className={`font-mono text-xs font-bold w-4 text-center ${m.color}`}>#{m.rank}</span>
                    <span className="text-xs font-medium text-foreground">{m.name}</span>
                  </div>
                  <span className="font-mono text-xs font-semibold text-emerald-400">{m.score}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="pt-4 border-t border-border/40">
            <Link 
              href="/benchmark"
              className="w-full flex items-center justify-center gap-2 p-2.5 rounded-lg bg-primary/10 hover:bg-primary/20 text-primary border border-primary/20 text-xs font-semibold transition-colors"
            >
              <Play className="w-3.5 h-3.5" /> Run Head-to-Head Test
            </Link>
          </div>
        </div>
      </div>

      {/* Recent Benchmark Runs Table */}
      <div className="glass-card p-6 rounded-xl border border-border/60 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
              <Clock className="w-5 h-5 text-primary" />
              Recent Evaluation Runs
            </h2>
            <p className="text-xs text-muted-foreground">Historical security sessions logged by RedGuard scanner</p>
          </div>

          <Link href="/history" className="text-xs font-mono text-primary hover:underline flex items-center gap-1">
            View All History <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-border/60 text-muted-foreground font-mono uppercase text-[10px]">
                <th className="pb-3 px-3">Run ID</th>
                <th className="pb-3 px-3">Target Agent</th>
                <th className="pb-3 px-3">Probes</th>
                <th className="pb-3 px-3">Resisted (Blocked)</th>
                <th className="pb-3 px-3">Compromised (ASR)</th>
                <th className="pb-3 px-3">Status</th>
                <th className="pb-3 px-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {sessions.slice(0, 5).map((s) => (
                <tr key={s.id} className="hover:bg-muted/40 transition-colors">
                  <td className="py-3.5 px-3 font-mono text-primary font-medium">{s.sessionId}</td>
                  <td className="py-3.5 px-3 font-medium text-foreground">{s.targetAgent}</td>
                  <td className="py-3.5 px-3 font-mono">{s.totalProbes}</td>
                  <td className="py-3.5 px-3 font-mono text-emerald-400 font-medium flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" /> {s.blocked}
                  </td>
                  <td className="py-3.5 px-3 font-mono text-rose-400 font-medium">
                    <span className="flex items-center gap-1">
                      <XCircle className="w-3.5 h-3.5" /> {s.allowed}
                    </span>
                  </td>
                  <td className="py-3.5 px-3">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono border ${
                      s.status === 'COMPLETED' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                    }`}>
                      {s.status}
                    </span>
                  </td>
                  <td className="py-3.5 px-3 text-right">
                    <Link 
                      href={`/results/${s.sessionId}`}
                      className="inline-flex items-center gap-1 text-primary hover:underline font-mono text-[11px]"
                    >
                      View Report <ArrowRight className="w-3 h-3" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
