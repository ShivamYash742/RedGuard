"use client"
import React, { useState } from 'react'
import { FileText, Download, Eye, Search, ShieldCheck, CheckCircle2 } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface ReportData {
  id: string
  sessionId: string
  title: string
  modelName: string
  createdAt: string
  totalProbes: number
  securityScore: number
  riskLevel: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  contentMarkdown: string
}

const MOCK_REPORTS: ReportData[] = [
  {
    id: 'rep-01',
    sessionId: 'run_20260804_143000',
    title: 'RedGuard Audit: Nemotron Super 70B',
    modelName: 'Nemotron Super 70B',
    createdAt: '2026-08-04T14:35:00Z',
    totalProbes: 93,
    securityScore: 83.8,
    riskLevel: 'MEDIUM',
    contentMarkdown: `# RedGuard Security Evaluation Audit Report

**Target Agent:** Nemotron Super 70B  
**Session ID:** run_20260804_143000  
**Evaluated At:** 2026-08-04 14:35:00 UTC  

---

## Executive Security Summary

RedGuard executed 93 adversarial attack probes across 8 core attack vector families. Nemotron Super 70B achieved an overall **Security Resilience Score of 83.8%**, blocking 78 attack probes and yielding an Attack Success Rate (ASR) of 16.2% (15 compromised probes).

### Key Vulnerability Highlights:
1. **Markdown Image Exfiltration (CRITICAL):** 2 probes successfully tricked the agent into outputting image tags with query parameters.
2. **Hidden HTML Comments (HIGH):** 3 indirect content injection probes bypassed refusal filters when embedded in HTML comments.

---

## Recommendations
- Enforce strict domain whitelisting on all Markdown image output renderers.
- Apply secondary LLM intent classification traps for indirect web retrieval payloads.
`
  },
  {
    id: 'rep-02',
    sessionId: 'run_20260804_110000',
    title: 'RedGuard Audit: GPT-4o Security Agent',
    modelName: 'GPT-4o Security Agent',
    createdAt: '2026-08-04T11:05:00Z',
    totalProbes: 93,
    securityScore: 90.3,
    riskLevel: 'LOW',
    contentMarkdown: `# RedGuard Security Audit Report: GPT-4o Agent

**Target Agent:** GPT-4o Security Agent  
**Session ID:** run_20260804_110000  
**Evaluated At:** 2026-08-04 11:05:00 UTC  

---

## Summary
GPT-4o demonstrated **90.3% resilience** against adversarial probes. 84 probes were successfully blocked by DPI regex traps and system refusal prompts.
`
  }
]

export default function AuditReportsPage() {
  const [search, setSearch] = useState('')
  const [selectedReport, setSelectedReport] = useState<ReportData | null>(null)

  const filteredReports = MOCK_REPORTS.filter(r => 
    r.title.toLowerCase().includes(search.toLowerCase()) ||
    r.modelName.toLowerCase().includes(search.toLowerCase()) ||
    r.sessionId.toLowerCase().includes(search.toLowerCase())
  )

  const downloadFile = (content: string, filename: string, type: string) => {
    const blob = new Blob([content], { type })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 text-xs font-mono text-indigo-400 uppercase tracking-widest mb-1">
          <FileText className="w-4 h-4" /> Compliance & Audit Export
        </div>
        <h1 className="text-3xl font-extrabold text-foreground tracking-tight">
          Security Audit Reports
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Preview and download structured JSON & Markdown security evaluation reports.
        </p>
      </div>

      {/* Filter */}
      <div className="flex items-center justify-between p-4 rounded-xl glass-card border border-border/60">
        <div className="relative w-full max-w-sm">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search reports by title, model, run ID..."
            className="w-full h-9 pl-9 pr-4 text-xs bg-card/60 border border-border/60 rounded-lg outline-none focus:border-primary text-foreground font-mono"
          />
        </div>
      </div>

      {/* Report Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {filteredReports.map(rep => (
          <div key={rep.id} className="glass-card-hover p-6 rounded-xl border border-border/60 space-y-4 flex flex-col justify-between">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs text-primary">{rep.sessionId}</span>
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                  rep.riskLevel === 'MEDIUM' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                }`}>
                  {rep.riskLevel} RISK
                </span>
              </div>

              <h3 className="text-lg font-bold text-foreground">{rep.title}</h3>

              <div className="grid grid-cols-2 gap-2 text-xs font-mono p-3 rounded-lg bg-card/40 border border-border/30">
                <div>
                  <span className="text-muted-foreground">Probes:</span>
                  <div className="font-bold text-foreground">{rep.totalProbes}</div>
                </div>
                <div>
                  <span className="text-muted-foreground">Security Score:</span>
                  <div className="font-bold text-emerald-400">{rep.securityScore}%</div>
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-border/40 flex items-center justify-between gap-2">
              <Button onClick={() => setSelectedReport(rep)} size="sm" variant="outline" className="gap-1.5 text-xs">
                <Eye className="w-3.5 h-3.5" /> Preview Report
              </Button>
              <div className="flex items-center gap-1">
                <Button 
                  onClick={() => downloadFile(rep.contentMarkdown, `${rep.sessionId}_report.md`, 'text/markdown')} 
                  size="sm" 
                  variant="ghost" 
                  className="gap-1 text-xs"
                >
                  <Download className="w-3.5 h-3.5" /> .MD
                </Button>
                <Button 
                  onClick={() => downloadFile(JSON.stringify(rep, null, 2), `${rep.sessionId}_report.json`, 'application/json')} 
                  size="sm" 
                  variant="ghost" 
                  className="gap-1 text-xs"
                >
                  <Download className="w-3.5 h-3.5" /> .JSON
                </Button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Markdown Preview Modal */}
      {selectedReport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm">
          <div className="relative w-full max-w-3xl max-h-[85vh] bg-card border border-border rounded-xl shadow-2xl flex flex-col overflow-hidden glass-card">
            <div className="flex items-center justify-between p-4 border-b border-border/60">
              <h3 className="font-bold text-base text-foreground">{selectedReport.title}</h3>
              <Button onClick={() => setSelectedReport(null)} size="sm" variant="ghost">Close</Button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 text-xs font-mono text-foreground space-y-4 whitespace-pre-wrap leading-relaxed">
              {selectedReport.contentMarkdown}
            </div>

            <div className="p-4 border-t border-border/60 flex items-center justify-end gap-2">
              <Button 
                onClick={() => downloadFile(selectedReport.contentMarkdown, `${selectedReport.sessionId}_report.md`, 'text/markdown')} 
                className="gap-2 bg-primary text-white"
              >
                <Download className="w-4 h-4" /> Download Markdown Report
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
