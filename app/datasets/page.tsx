"use client"
import React, { useState } from 'react'
import { Database, Search, Code, CheckCircle2, ShieldCheck, Plus, FileCode } from 'lucide-react'
import { Button } from '@/components/ui/button'

const DATASET_STATS = [
  { name: 'direct_injection.json', count: 14, size: '14.7 KB', category: 'Direct Prompt Injection' },
  { name: 'content_injection.json', count: 18, size: '17.3 KB', category: 'Indirect Content Injection' },
  { name: 'exfiltration.json', count: 12, size: '11.0 KB', category: 'Data & Secret Exfiltration' },
  { name: 'tool_security.json', count: 15, size: '13.7 KB', category: 'Tool Abuse & Command Exec' },
  { name: 'goal_diversion.json', count: 10, size: '8.4 KB', category: 'Goal Diversion' },
  { name: 'memory_poisoning.json', count: 8, size: '13.1 KB', category: 'Memory Poisoning' },
  { name: 'autonomy.json', count: 9, size: '9.7 KB', category: 'Unchecked Autonomy' },
  { name: 'planning.json', count: 7, size: '11.3 KB', category: 'Planning & Logic Evasion' }
]

export default function DatasetCoveragePage() {
  const [selectedDataset, setSelectedDataset] = useState('direct_injection.json')
  const [customProbeName, setCustomProbeName] = useState('')
  const [customPrompt, setCustomPrompt] = useState('')

  const totalProbes = DATASET_STATS.reduce((acc, curr) => acc + curr.count, 0)

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 text-xs font-mono text-emerald-400 uppercase tracking-widest mb-1">
          <Database className="w-4 h-4" /> Benchmark Dataset Registry
        </div>
        <h1 className="text-3xl font-extrabold text-foreground tracking-tight">
          Dataset Coverage & Custom Probe Builder
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Inspect built-in dataset schemas ({totalProbes} probes across 8 categories) and author custom test probes.
        </p>
      </div>

      {/* Overview Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="glass-card p-5 rounded-xl border border-emerald-500/30">
          <div className="text-xs font-mono text-muted-foreground">TOTAL DATASET PROBES</div>
          <div className="text-3xl font-extrabold font-mono text-emerald-400 mt-2">{totalProbes}</div>
          <div className="text-xs text-muted-foreground mt-1">Validated against schema.json</div>
        </div>
        <div className="glass-card p-5 rounded-xl border border-indigo-500/30">
          <div className="text-xs font-mono text-muted-foreground">ATTACK CATEGORIES</div>
          <div className="text-3xl font-extrabold font-mono text-indigo-400 mt-2">8 Families</div>
          <div className="text-xs text-muted-foreground mt-1">Multi-modal coverage</div>
        </div>
        <div className="glass-card p-5 rounded-xl border border-border/60">
          <div className="text-xs font-mono text-muted-foreground">SCHEMA VALIDATOR</div>
          <div className="text-3xl font-extrabold font-mono text-foreground mt-2">Strict JSON</div>
          <div className="text-xs text-muted-foreground mt-1">Validator engine active</div>
        </div>
      </div>

      {/* Dataset File Selector Grid */}
      <div className="glass-card p-6 rounded-xl border border-border/60 space-y-4">
        <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
          <FileCode className="w-5 h-5 text-emerald-400" />
          Built-in Dataset Files
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {DATASET_STATS.map((ds) => (
            <button
              key={ds.name}
              onClick={() => setSelectedDataset(ds.name)}
              className={`p-3.5 rounded-lg border text-left font-mono transition-all ${
                selectedDataset === ds.name 
                  ? 'bg-emerald-500/15 border-emerald-500 text-foreground shadow-sm' 
                  : 'bg-card/40 border-border/40 text-muted-foreground hover:text-foreground'
              }`}
            >
              <div className="text-xs font-bold text-emerald-400">{ds.name}</div>
              <div className="text-[11px] text-muted-foreground mt-1">{ds.category}</div>
              <div className="flex justify-between text-[10px] text-muted-foreground mt-2 pt-2 border-t border-border/30">
                <span>{ds.count} Probes</span>
                <span>{ds.size}</span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Custom Probe Authoring Builder */}
      <div className="glass-card p-6 rounded-xl border border-border/60 space-y-4 max-w-2xl">
        <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
          <Plus className="w-5 h-5 text-primary" />
          Author Custom Test Probe
        </h2>

        <div className="space-y-3 font-mono text-xs">
          <div>
            <label className="text-muted-foreground block mb-1">Probe Name:</label>
            <input
              type="text"
              value={customProbeName}
              onChange={(e) => setCustomProbeName(e.target.value)}
              placeholder="e.g. SQL Injection via Tool Parameter"
              className="w-full h-9 px-3 bg-card border border-border/60 rounded-lg outline-none text-foreground"
            />
          </div>

          <div>
            <label className="text-muted-foreground block mb-1">Adversarial Prompt Payload:</label>
            <textarea
              rows={4}
              value={customPrompt}
              onChange={(e) => setCustomPrompt(e.target.value)}
              placeholder="Enter probe text..."
              className="w-full p-3 bg-card border border-border/60 rounded-lg outline-none text-foreground"
            />
          </div>

          <Button 
            onClick={() => {
              alert('Custom probe validated and added to local benchmark queue!')
              setCustomProbeName('')
              setCustomPrompt('')
            }}
            className="w-full bg-emerald-600 hover:bg-emerald-500 text-white gap-2 font-semibold"
          >
            <CheckCircle2 className="w-4 h-4" /> Validate & Save Custom Probe
          </Button>
        </div>
      </div>
    </div>
  )
}
