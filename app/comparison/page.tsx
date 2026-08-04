"use client"
import React, { useState } from 'react'
import { Trophy, Search, ArrowUpDown, ShieldCheck, Zap, AlertTriangle, Scale } from 'lucide-react'
import { MOCK_LEADERBOARD, ModelScoreCard } from '@/lib/data-service'
import { Button } from '@/components/ui/button'

export default function ModelComparisonPage() {
  const [search, setSearch] = useState('')
  const [sortField, setSortField] = useState<keyof ModelScoreCard>('securityScore')
  const [sortAsc, setSortAsc] = useState(false)

  // Comparison State
  const [modelA, setModelA] = useState<string>('m1')
  const [modelB, setModelB] = useState<string>('m3')

  const handleSort = (field: keyof ModelScoreCard) => {
    if (sortField === field) {
      setSortAsc(!sortAsc)
    } else {
      setSortField(field)
      setSortAsc(false)
    }
  }

  const sortedModels = [...MOCK_LEADERBOARD].filter(m => 
    m.modelName.toLowerCase().includes(search.toLowerCase()) ||
    m.provider.toLowerCase().includes(search.toLowerCase())
  ).sort((a, b) => {
    const valA = a[sortField]
    const valB = b[sortField]
    if (typeof valA === 'number' && typeof valB === 'number') {
      return sortAsc ? valA - valB : valB - valA
    }
    return 0
  })

  const mA = MOCK_LEADERBOARD.find(m => m.id === modelA) || MOCK_LEADERBOARD[0]
  const mB = MOCK_LEADERBOARD.find(m => m.id === modelB) || MOCK_LEADERBOARD[2]

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 text-xs font-mono text-amber-400 uppercase tracking-widest mb-1">
          <Trophy className="w-4 h-4" /> AI Safety Benchmark Leaderboard
        </div>
        <h1 className="text-3xl font-extrabold text-foreground tracking-tight">
          Model Comparison & Resilience Leaderboard
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Compare red-teaming security resilience, attack success rate (ASR), and latency across LLM models.
        </p>
      </div>

      {/* Leaderboard Table */}
      <div className="glass-card p-6 rounded-xl border border-border/60 space-y-4">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <Trophy className="w-5 h-5 text-amber-400" />
            Rankings Table
          </h2>

          <div className="relative w-full sm:w-72">
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter by model or provider..."
              className="w-full h-9 pl-9 pr-4 text-xs bg-card/60 border border-border/60 rounded-lg outline-none focus:border-primary text-foreground placeholder:text-muted-foreground font-mono"
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-border/60 text-muted-foreground font-mono uppercase text-[10px]">
                <th className="pb-3 px-3">Rank</th>
                <th className="pb-3 px-3 cursor-pointer hover:text-foreground" onClick={() => handleSort('modelName')}>
                  Model Name <ArrowUpDown className="inline w-3 h-3 ml-1" />
                </th>
                <th className="pb-3 px-3 cursor-pointer hover:text-foreground" onClick={() => handleSort('provider')}>
                  Provider <ArrowUpDown className="inline w-3 h-3 ml-1" />
                </th>
                <th className="pb-3 px-3 cursor-pointer hover:text-foreground text-right" onClick={() => handleSort('securityScore')}>
                  Security Score <ArrowUpDown className="inline w-3 h-3 ml-1" />
                </th>
                <th className="pb-3 px-3 cursor-pointer hover:text-foreground text-right" onClick={() => handleSort('asr')}>
                  ASR (%) <ArrowUpDown className="inline w-3 h-3 ml-1" />
                </th>
                <th className="pb-3 px-3 cursor-pointer hover:text-foreground text-right" onClick={() => handleSort('avgLatencyMs')}>
                  Latency (ms) <ArrowUpDown className="inline w-3 h-3 ml-1" />
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {sortedModels.map((m, idx) => (
                <tr key={m.id} className="hover:bg-muted/40 transition-colors">
                  <td className="py-3.5 px-3 font-mono font-bold text-amber-400">#{idx + 1}</td>
                  <td className="py-3.5 px-3 font-semibold text-foreground">{m.modelName}</td>
                  <td className="py-3.5 px-3 text-muted-foreground font-mono">{m.provider}</td>
                  <td className="py-3.5 px-3 text-right font-mono font-bold text-emerald-400">{m.securityScore}%</td>
                  <td className="py-3.5 px-3 text-right font-mono font-bold text-rose-400">{m.asr}%</td>
                  <td className="py-3.5 px-3 text-right font-mono text-muted-foreground">{m.avgLatencyMs}ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Head-to-Head Comparison Card */}
      <div className="glass-card p-6 rounded-xl border border-border/60 space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <Scale className="w-5 h-5 text-indigo-400" />
            Head-to-Head Model Comparator
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 rounded-xl bg-card/40 border border-border/40">
          <div>
            <label className="text-xs font-mono text-muted-foreground mb-1 block">Model A:</label>
            <select
              value={modelA}
              onChange={(e) => setModelA(e.target.value)}
              className="w-full h-10 px-3 bg-card border border-border/60 rounded-lg text-xs font-mono text-foreground outline-none"
            >
              {MOCK_LEADERBOARD.map(m => (
                <option key={m.id} value={m.id}>{m.modelName} ({m.provider})</option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-xs font-mono text-muted-foreground mb-1 block">Model B:</label>
            <select
              value={modelB}
              onChange={(e) => setModelB(e.target.value)}
              className="w-full h-10 px-3 bg-card border border-border/60 rounded-lg text-xs font-mono text-foreground outline-none"
            >
              {MOCK_LEADERBOARD.map(m => (
                <option key={m.id} value={m.id}>{m.modelName} ({m.provider})</option>
              ))}
            </select>
          </div>
        </div>

        {/* Side by side metric grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="p-5 rounded-xl bg-card/60 border border-indigo-500/30 space-y-3">
            <div className="font-bold text-base text-foreground">{mA.modelName}</div>
            <div className="text-xs text-muted-foreground">{mA.provider}</div>

            <div className="space-y-2 pt-2 font-mono text-xs">
              <div className="flex justify-between">
                <span>Security Resilience:</span>
                <span className="text-emerald-400 font-bold">{mA.securityScore}%</span>
              </div>
              <div className="flex justify-between">
                <span>Attack Success Rate:</span>
                <span className="text-rose-400 font-bold">{mA.asr}%</span>
              </div>
              <div className="flex justify-between">
                <span>Average Response Latency:</span>
                <span>{mA.avgLatencyMs}ms</span>
              </div>
            </div>
          </div>

          <div className="p-5 rounded-xl bg-card/60 border border-cyan-500/30 space-y-3">
            <div className="font-bold text-base text-foreground">{mB.modelName}</div>
            <div className="text-xs text-muted-foreground">{mB.provider}</div>

            <div className="space-y-2 pt-2 font-mono text-xs">
              <div className="flex justify-between">
                <span>Security Resilience:</span>
                <span className="text-emerald-400 font-bold">{mB.securityScore}%</span>
              </div>
              <div className="flex justify-between">
                <span>Attack Success Rate:</span>
                <span className="text-rose-400 font-bold">{mB.asr}%</span>
              </div>
              <div className="flex justify-between">
                <span>Average Response Latency:</span>
                <span>{mB.avgLatencyMs}ms</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
