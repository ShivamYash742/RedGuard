"use client"
import React, { Suspense, useState, useEffect } from 'react'
import { useSearchParams } from 'next/navigation'
import {
  Settings as SettingsIcon, Server, Database, RefreshCw,
  BookOpen, Save, Copy, Check, Code,
  ChevronDown, ChevronUp,
} from 'lucide-react'
import { KNOWN_AGENTS } from '@/lib/data-service'
import { TableSkeleton } from '@/components/Skeletons'
import EmptyState from '@/components/EmptyState'

type Tab = 'system' | 'policy' | 'audit'

function SettingsContent() {
  const searchParams = useSearchParams()
  const initialTab = (searchParams.get('tab') as Tab) || 'system'
  const [tab, setTab] = useState<Tab>(initialTab)

  const tabs: { id: Tab; label: string }[] = [
    { id: 'system', label: 'System' },
    { id: 'policy', label: 'Policy & Citation' },
    { id: 'audit', label: 'Audit Log' },
  ]

  return (
    <div className="space-y-6">
      <div className="border-b border-[var(--border-subtle)] pb-4">
        <div className="flex items-center gap-2 text-xs font-semibold text-[var(--primary)] uppercase tracking-wider mb-1">
          <SettingsIcon className="h-4 w-4" /> System Configuration
        </div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-tight">Settings</h1>
        <p className="text-xs text-[var(--text-secondary)] mt-0.5">
          Infrastructure health, configured agents, guardrail policy, and the inspector&apos;s audit trail.
        </p>
      </div>

      <div className="flex items-center gap-1 border-b border-[var(--border-subtle)]">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-3 py-2 text-xs font-semibold border-b-2 -mb-px transition-colors ${
              tab === t.id
                ? 'border-[var(--primary)] text-[var(--primary)]'
                : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'system' && <SystemTab />}
      {tab === 'policy' && <PolicyTab />}
      {tab === 'audit' && <AuditTab />}
    </div>
  )
}

export default function SettingsPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-xs">Loading settings...</div>}>
      <SettingsContent />
    </Suspense>
  )
}

function SystemTab() {
  const [health, setHealth] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const checkHealth = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/health')
      if (res.ok) setHealth(await res.json())
      else setHealth({ status: 'error', db_connected: false })
    } catch {
      setHealth({ status: 'offline', db_connected: false })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    checkHealth()
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex justify-end">
        <button
          onClick={checkHealth}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius)] border border-[var(--border-default)] bg-[var(--surface-raised)] text-xs font-semibold text-[var(--text-primary)] hover:bg-[var(--surface-base)] transition-colors"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh Health
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="research-card space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] flex items-center gap-1.5">
              <Server className="h-4 w-4 text-[var(--primary)]" /> FastAPI Backend Service
            </span>
            <span className={`badge-semantic ${health?.status === 'ok' ? 'badge-success' : 'badge-danger'}`}>
              {health?.status === 'ok' ? 'ONLINE (Port 8000)' : 'OFFLINE'}
            </span>
          </div>
          <p className="text-xs text-[var(--text-secondary)]">
            Proxies SSE evaluation streams & proxy inspect middleware at <code className="font-mono text-[11px]">http://localhost:8000</code>.
          </p>
        </div>

        <div className="research-card space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] flex items-center gap-1.5">
              <Database className="h-4 w-4 text-[var(--primary)]" /> Database Connection Status
            </span>
            <span className={`badge-semantic ${health?.db_connected ? 'badge-success' : 'badge-danger'}`}>
              {health?.db_connected ? 'CONNECTED (Prisma SQLite)' : 'DISCONNECTED'}
            </span>
          </div>
          <p className="text-xs text-[var(--text-secondary)]">
            Stores session run histories, probe audit events, and generated benchmark security reports.
          </p>
        </div>
      </div>

      <div className="research-card space-y-4">
        <h2 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider">
          Configured Model & Agent Endpoints
        </h2>
        <div className="overflow-x-auto rounded-[var(--radius)] border border-[var(--border-subtle)]">
          <table className="research-table">
            <thead>
              <tr>
                <th>Agent Identifier</th>
                <th>Target Agent Name</th>
                <th>Provider</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {KNOWN_AGENTS.map(agent => (
                <tr key={agent.id}>
                  <td className="font-mono text-xs text-[var(--primary)] font-semibold">{agent.id}</td>
                  <td className="font-bold text-xs">{agent.name}</td>
                  <td className="font-mono text-xs text-[var(--text-secondary)]">{agent.badge}</td>
                  <td><span className="badge-semantic badge-success">CONFIGURED</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function PolicyTab() {
  const [yaml, setYaml] = useState('')
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')
  const [copiedBib, setCopiedBib] = useState(false)

  useEffect(() => {
    async function loadPolicy() {
      try {
        const res = await fetch('/api/policy')
        if (res.ok) {
          const data = await res.json()
          setYaml(data.yaml || '')
        }
      } catch (err) {
        console.error('Failed to load policy:', err)
      } finally {
        setLoading(false)
      }
    }
    loadPolicy()
  }, [])

  const savePolicy = async () => {
    setSaving(true)
    setMessage('')
    try {
      const res = await fetch('/api/policy', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ yaml }),
      })
      setMessage(res.ok ? 'Policy saved successfully.' : 'Failed to save policy.')
    } catch (err) {
      setMessage('Error saving policy.')
      console.error(err)
    } finally {
      setSaving(false)
      setTimeout(() => setMessage(''), 3000)
    }
  }

  const bibtex = `@article{redguard2024,
  title={RedGuard: A Comprehensive Security Evaluation Benchmark for Autonomous LLM Agents},
  author={RedGuard Research Team},
  journal={arXiv preprint arXiv:2408.00000},
  year={2024}
}`

  const copyBibtex = () => {
    navigator.clipboard.writeText(bibtex)
    setCopiedBib(true)
    setTimeout(() => setCopiedBib(false), 2000)
  }

  if (loading) return <div className="p-8 text-center text-xs">Loading policy configuration...</div>

  return (
    <div className="space-y-6">
      <div className="flex justify-end items-center gap-3">
        {message && (
          <span className={`text-xs font-semibold ${message.includes('success') ? 'text-[var(--success)]' : 'text-[var(--danger)]'}`}>
            {message}
          </span>
        )}
        <button
          onClick={savePolicy}
          disabled={saving}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-[var(--radius)] bg-[var(--primary)] text-[var(--primary-foreground)] text-xs font-semibold hover:bg-[var(--primary-hover)] transition-colors"
        >
          <Save className="h-3.5 w-3.5" />
          {saving ? 'Saving YAML...' : 'Save Security Policy'}
        </button>
      </div>

      <div className="research-card space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider flex items-center gap-1.5">
            <Code className="h-4 w-4 text-[var(--primary)]" /> How to Cite RedGuard Benchmark
          </h2>
          <button
            onClick={copyBibtex}
            className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--primary)] hover:underline"
          >
            {copiedBib ? <Check className="h-3.5 w-3.5 text-[var(--success)]" /> : <Copy className="h-3.5 w-3.5" />}
            {copiedBib ? 'BibTeX Copied' : 'Copy BibTeX Citation'}
          </button>
        </div>
        <pre className="p-3 rounded-[var(--radius)] bg-[var(--surface-base)] border border-[var(--border-subtle)] font-mono text-xs text-[var(--text-secondary)]">
          {bibtex}
        </pre>
        <p className="text-[11px] text-[var(--text-muted)] flex items-center gap-1.5">
          <BookOpen className="h-3 w-3" /> The arXiv id above is a placeholder pending submission.
        </p>
      </div>

      <div className="research-card space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider">
            Active Security Guardrail Rules (<code className="font-mono text-xs">policy.yaml</code>)
          </h2>
          <span className="text-xs text-[var(--text-muted)]">Changes apply dynamically to proxy inspect operations</span>
        </div>

        <textarea
          value={yaml}
          onChange={e => setYaml(e.target.value)}
          rows={16}
          className="w-full rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-base)] p-4 font-mono text-xs text-[var(--text-primary)] focus:outline-none focus:border-[var(--primary)] leading-relaxed resize-y"
        />
      </div>
    </div>
  )
}

function AuditTab() {
  const [events, setEvents] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedRow, setExpandedRow] = useState<string | null>(null)

  useEffect(() => {
    async function loadEvents() {
      try {
        const res = await fetch('/api/events')
        if (res.ok) setEvents(await res.json())
      } catch (err) {
        console.error('Failed to load events', err)
      } finally {
        setLoading(false)
      }
    }
    loadEvents()
  }, [])

  if (loading) return <TableSkeleton rows={6} />
  if (events.length === 0) {
    return (
      <EmptyState
        title="No audit events recorded"
        description="Inspector events appear here once traffic passes through the proxy inspect middleware."
        icon="inbox"
      />
    )
  }

  return (
    <div className="overflow-x-auto rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)]">
      <table className="research-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>Category</th>
            <th>Status</th>
            <th>Risk Score</th>
            <th>ML Verdict</th>
            <th>Rule</th>
            <th className="text-center">Details</th>
          </tr>
        </thead>
        <tbody>
          {events.map((evt) => {
            const isExpanded = expandedRow === evt.id
            return (
              <React.Fragment key={evt.id}>
                <tr
                  onClick={() => setExpandedRow(isExpanded ? null : evt.id)}
                  className="cursor-pointer hover:bg-[var(--surface-base)] transition-colors"
                >
                  <td className="text-xs text-[var(--text-secondary)]">{new Date(evt.timestamp).toLocaleString()}</td>
                  <td className="text-xs font-medium capitalize text-[var(--text-primary)]">{evt.category}</td>
                  <td>
                    <span className={`badge-semantic ${evt.status === 'BLOCKED' ? 'badge-success' : 'badge-danger'}`}>
                      {evt.status}
                    </span>
                  </td>
                  <td className="font-mono text-xs font-semibold text-[var(--text-primary)]">{evt.regexRiskScore.toFixed(2)}</td>
                  <td className="text-xs text-[var(--text-secondary)]">{evt.classifierVerdict || 'N/A'}</td>
                  <td className="font-mono text-xs text-[var(--text-muted)]">{evt.matchedRule || '-'}</td>
                  <td className="text-center text-[var(--text-muted)]">
                    {isExpanded ? <ChevronUp className="h-3.5 w-3.5 inline" /> : <ChevronDown className="h-3.5 w-3.5 inline" />}
                  </td>
                </tr>
                {isExpanded && (
                  <tr>
                    <td colSpan={7} className="bg-[var(--surface-base)] p-4">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)] mb-2">Prompt</h4>
                          <pre className="whitespace-pre-wrap break-words font-mono text-xs bg-[var(--surface-raised)] border border-[var(--border-subtle)] p-3 rounded-[var(--radius)] text-[var(--text-primary)]">
                            {evt.promptText}
                          </pre>
                        </div>
                        <div>
                          <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)] mb-2">Analysis Details</h4>
                          <div className="bg-[var(--surface-raised)] border border-[var(--border-subtle)] p-3 rounded-[var(--radius)] text-xs space-y-1.5">
                            <div><span className="text-[var(--text-muted)]">Declared Intent:</span> <span className="text-[var(--text-primary)] font-medium">{evt.declaredIntent}</span></div>
                            <div><span className="text-[var(--text-muted)]">Detected Intent:</span> <span className="text-[var(--text-primary)] font-medium">{evt.detectedIntent}</span></div>
                            <div><span className="text-[var(--text-muted)]">Mismatch:</span> <span className={evt.mismatch ? 'text-[var(--danger)] font-semibold' : 'text-[var(--text-primary)] font-medium'}>{evt.mismatch ? 'Yes' : 'No'}</span></div>
                            <div><span className="text-[var(--text-muted)]">ML Score:</span> <span className="text-[var(--text-primary)] font-medium">{evt.classifierScore ? evt.classifierScore.toFixed(4) : 'N/A'}</span></div>
                            <div><span className="text-[var(--text-muted)]">Event Hash:</span> <span className="font-mono text-[var(--text-primary)]">{evt.eventHash.substring(0, 16)}...</span></div>
                          </div>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
