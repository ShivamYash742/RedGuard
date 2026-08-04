"use client"
import React, { useState } from 'react'
import Link from 'next/link'
import { Terminal, Search, ArrowRight, ShieldAlert, Code, CheckCircle2, Filter } from 'lucide-react'
import { MOCK_PROBES, ProbeDetail } from '@/lib/data-service'
import { Button } from '@/components/ui/button'

export default function ProbesDirectoryPage() {
  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('ALL')
  const [severityFilter, setSeverityFilter] = useState('ALL')

  const filteredProbes = MOCK_PROBES.filter(p => {
    const matchesSearch = p.name.toLowerCase().includes(search.toLowerCase()) ||
                          p.prompt.toLowerCase().includes(search.toLowerCase()) ||
                          p.id.toLowerCase().includes(search.toLowerCase())
    const matchesCat = categoryFilter === 'ALL' || p.category === categoryFilter
    const matchesSev = severityFilter === 'ALL' || p.severity === severityFilter
    return matchesSearch && matchesCat && matchesSev
  })

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono text-primary uppercase tracking-widest mb-1">
            <Terminal className="w-4 h-4" /> Adversarial Payload Registry
          </div>
          <h1 className="text-3xl font-extrabold text-foreground tracking-tight">
            Probes Directory & Traps
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Inspect raw attack prompts, regex rules, expected refusals, and ML intent tags.
          </p>
        </div>

        <Link href="/benchmark">
          <Button className="gap-2 bg-primary hover:bg-primary/90 text-white shadow-lg shadow-primary/20">
            <Terminal className="w-4 h-4" /> Run Probe Test
          </Button>
        </Link>
      </div>

      {/* Filter Controls */}
      <div className="flex flex-col md:flex-row items-center justify-between gap-4 p-4 rounded-xl glass-card border border-border/60">
        <div className="relative w-full md:w-96">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by probe name, prompt text, or ID..."
            className="w-full h-9 pl-9 pr-4 text-xs bg-card/60 border border-border/60 rounded-lg outline-none focus:border-primary text-foreground placeholder:text-muted-foreground"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
          {/* Category Selector */}
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="h-9 px-3 text-xs bg-card border border-border/60 rounded-lg outline-none text-foreground font-mono"
          >
            <option value="ALL">All Categories</option>
            <option value="direct_injection">Direct Injection</option>
            <option value="content_injection">Content Injection</option>
            <option value="exfiltration">Exfiltration</option>
            <option value="tool_security">Tool Abuse</option>
            <option value="goal_diversion">Goal Diversion</option>
          </select>

          {/* Severity Selector */}
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="h-9 px-3 text-xs bg-card border border-border/60 rounded-lg outline-none text-foreground font-mono"
          >
            <option value="ALL">All Severities</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>
        </div>
      </div>

      {/* Probes Table */}
      <div className="glass-card p-6 rounded-xl border border-border/60 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
            <Code className="w-4 h-4 text-primary" />
            Showing {filteredProbes.length} Registered Probes
          </h2>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-border/60 text-muted-foreground font-mono uppercase text-[10px]">
                <th className="pb-3 px-3">Probe ID</th>
                <th className="pb-3 px-3">Name</th>
                <th className="pb-3 px-3">Category</th>
                <th className="pb-3 px-3">Severity</th>
                <th className="pb-3 px-3">Raw Payload</th>
                <th className="pb-3 px-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {filteredProbes.map((p) => (
                <tr key={p.id} className="hover:bg-muted/40 transition-colors">
                  <td className="py-3.5 px-3 font-mono text-primary font-medium">{p.id}</td>
                  <td className="py-3.5 px-3 font-medium text-foreground">{p.name}</td>
                  <td className="py-3.5 px-3 font-mono text-muted-foreground">{p.category}</td>
                  <td className="py-3.5 px-3">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-mono border ${
                      p.severity === 'CRITICAL' ? 'bg-rose-500/10 text-rose-400 border-rose-500/20' : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                    }`}>
                      {p.severity}
                    </span>
                  </td>
                  <td className="py-3.5 px-3 font-mono text-muted-foreground max-w-xs truncate">
                    {p.prompt}
                  </td>
                  <td className="py-3.5 px-3 text-right">
                    <Link
                      href={`/probes/${p.id}`}
                      className="inline-flex items-center gap-1 text-primary hover:underline font-mono text-[11px]"
                    >
                      Metadata <ArrowRight className="w-3 h-3" />
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
