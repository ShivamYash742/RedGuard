"use client"
import React, { use } from 'react'
import Link from 'next/link'
import { benchmarkDataService, Probe } from '@/lib/scanner_mode/data-service'
import { ArrowLeft, CheckCircle2, ShieldAlert, BookOpen, ExternalLink, Copy, Check } from 'lucide-react'

export default function ProbeDetailPage({ params }: { params: Promise<{ probeId: string }> }) {
  const resolvedParams = use(params)
  const probeId = resolvedParams.probeId
  const probe: Probe | undefined = benchmarkDataService.getProbeById(probeId)
  const [copied, setCopied] = React.useState(false)

  if (!probe) {
    return (
      <div className="p-8 text-center space-y-4">
        <h2 className="text-xl font-bold">Probe Not Found</h2>
        <p className="text-sm text-[var(--text-secondary)]">Probe ID &quot;{probeId}&quot; does not exist in the dataset.</p>
        <Link href="/corpus" className="text-xs text-[var(--primary)] font-semibold hover:underline">
          ← Return to Corpus
        </Link>
      </div>
    )
  }

  // An indirect probe's attack text is the result of a tool the agent reads; the user message is an ordinary request.
  const planted = Object.entries(probe.tool_fixtures ?? {})

  const copyPrompt = () => {
    navigator.clipboard.writeText([probe.prompt, ...planted.map(([tool, text]) => `[${tool} tool result]\n${text}`)].join('\n\n'))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="space-y-6">
      {/* Navigation & Header */}
      <div>
        <Link href="/corpus" className="inline-flex items-center gap-1 text-xs text-[var(--primary)] font-semibold hover:underline mb-2">
          <ArrowLeft className="h-3 w-3" /> Back to Corpus
        </Link>

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[var(--border-subtle)] pb-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded-[var(--radius)] bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/20">
                {probe.id}
              </span>
              <span className="badge-semantic badge-neutral capitalize">{probe.attack_family.replace(/_/g, ' ')}</span>
              <span className="badge-semantic badge-neutral uppercase font-mono">{probe.difficulty}</span>
              {probe.benign_control && (
                <span className="badge-semantic badge-neutral" title="Harmless request: a refusal counts as over-refusal">benign control</span>
              )}
            </div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">{probe.title}</h1>
          </div>

          <div className="flex items-center gap-2 font-mono text-xs">
            <span className="research-card py-1 px-3 text-center">
              <span className="text-[var(--text-muted)] block text-[10px] uppercase">Scenario</span>
              <span className="font-bold text-xs capitalize">{probe.scenario.replace(/_/g, ' ')}</span>
            </span>
            <span className="research-card py-1 px-3 text-center">
              <span className="text-[var(--text-muted)] block text-[10px] uppercase">Probe Version</span>
              <span className="font-bold text-xs">{probe.probe_version || '1.0.0'}</span>
            </span>
          </div>
        </div>
      </div>

      {/* Metadata Specification Panel */}
      <div className="research-card space-y-4">
        <h2 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider">Probe Specification & Threat Model</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs bg-[var(--surface-base)] p-4 rounded-[var(--radius)] border border-[var(--border-subtle)]">
          <div>
            <span className="text-[var(--text-muted)] block uppercase font-medium">Attack Variant</span>
            <span className="font-mono text-[var(--text-primary)] font-semibold">{probe.attack_variant}</span>
          </div>
          <div>
            <span className="text-[var(--text-muted)] block uppercase font-medium">Threat Model</span>
            <span className="font-semibold text-[var(--text-primary)] capitalize">{probe.threat_model.replace(/_/g, ' ')}</span>
          </div>
          <div>
            <span className="text-[var(--text-muted)] block uppercase font-medium">Attacker Capability</span>
            <span className="font-semibold text-[var(--text-primary)] capitalize">{probe.attacker_capability || 'Prompt Level'}</span>
          </div>
          <div>
            <span className="text-[var(--text-muted)] block uppercase font-medium">Affected Layers</span>
            <span className="font-mono text-[var(--text-primary)]">{(probe.affected_layers || []).join(', ')}</span>
          </div>
        </div>
      </div>

      {/* Adversarial Payload Prompt */}
      <div className="research-card space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider">Adversarial Prompt Payload</h2>
          <button
            onClick={copyPrompt}
            className="flex items-center gap-1 text-xs text-[var(--primary)] font-semibold hover:underline"
          >
            {copied ? <Check className="h-3.5 w-3.5 text-[var(--success)]" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? 'Copied to Clipboard' : 'Copy Payload'}
          </button>
        </div>
        <div className="font-mono text-xs bg-[var(--surface-base)] border border-[var(--border-subtle)] p-4 rounded-[var(--radius)] text-[var(--text-primary)] whitespace-pre-wrap break-words">
          {probe.prompt}
        </div>
        {planted.map(([tool, text]) => (
          <div key={tool}>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)] mb-1">
              Planted result of the <span className="font-mono">{tool}</span> tool
            </h3>
            <div className="font-mono text-xs bg-[var(--surface-base)] border border-[var(--border-subtle)] p-4 rounded-[var(--radius)] text-[var(--text-primary)] whitespace-pre-wrap break-words">
              {text}
            </div>
          </div>
        ))}
      </div>

      {/* Expected vs Failure Behavior */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="research-card bg-[var(--success-bg)] space-y-2">
          <div className="flex items-center gap-1.5 text-xs font-bold text-[var(--success)]">
            <CheckCircle2 className="h-4 w-4" /> Expected Secure Behavior
          </div>
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed">{probe.expected_behavior}</p>
        </div>

        <div className="research-card bg-[var(--danger-bg)] space-y-2">
          <div className="flex items-center gap-1.5 text-xs font-bold text-[var(--danger)]">
            <ShieldAlert className="h-4 w-4" /> Failure / Compromise Behavior
          </div>
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed">{probe.failure_behavior}</p>
        </div>
      </div>

      {/* Research References */}
      {probe.references && probe.references.length > 0 && (
        <div className="research-card space-y-3">
          <h2 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider flex items-center gap-1.5">
            <BookOpen className="h-4 w-4 text-[var(--primary)]" /> Source Papers & References
          </h2>
          <div className="space-y-2">
            {probe.references.map((ref, idx) => (
              <div key={idx} className="p-3 rounded-[var(--radius)] bg-[var(--surface-base)] border border-[var(--border-subtle)] text-xs space-y-1">
                <div className="font-semibold text-[var(--text-primary)]">{ref.title}</div>
                <div className="text-[var(--text-secondary)]">
                  {ref.authors ? ref.authors.join(', ') : 'Research Team'} ({ref.year}) — <span className="italic">{ref.venue}</span>
                </div>
                {ref.url && (
                  <a href={ref.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[var(--primary)] hover:underline text-[11px] font-medium pt-1">
                    Open arXiv Publication <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
