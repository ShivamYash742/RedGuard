"use client"
import React, { useState, useEffect } from 'react'
import { Settings, Activity, Database, Server, CheckCircle2, XCircle, RefreshCw } from 'lucide-react'

export default function SettingsPage() {
  const [health, setHealth] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  const checkHealth = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/health')
      if (res.ok) setHealth(await res.json())
      else setHealth({ status: 'error', db_connected: false })
    } catch (e) {
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
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold text-[var(--primary)] uppercase tracking-wider mb-1">
            <Settings className="h-4 w-4" /> System Configuration
          </div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-tight">Settings & Infrastructure Health</h1>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Monitor FastAPI proxy connections, database status, & LLM agent model configurations.
          </p>
        </div>

        <button
          onClick={checkHealth}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-[var(--border-default)] bg-[var(--surface-raised)] text-xs font-semibold text-[var(--text-primary)] hover:bg-[var(--surface-base)] transition-colors"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh Health
        </button>
      </div>

      {/* Backend Status Cards */}
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
              <Database className="h-4 w-4 text-emerald-500" /> Database Connection Status
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

      {/* Configured Agent Endpoints */}
      <div className="research-card space-y-4">
        <h2 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider">
          Configured Model & Agent Endpoints
        </h2>
        <div className="overflow-x-auto rounded-lg border border-[var(--border-subtle)]">
          <table className="research-table">
            <thead>
              <tr>
                <th>Agent Identifier</th>
                <th>Target Agent Name</th>
                <th>Provider / Endpoint</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="font-mono text-xs text-[var(--primary)] font-semibold">nemotron_3_ultra</td>
                <td className="font-bold text-xs">Nemotron-3 Ultra (550B)</td>
                <td className="font-mono text-xs text-[var(--text-secondary)]">NVIDIA NIM Cloud API</td>
                <td><span className="badge-semantic badge-success">ACTIVE</span></td>
              </tr>
              <tr>
                <td className="font-mono text-xs text-[var(--primary)] font-semibold">nemotron_super_agent</td>
                <td className="font-bold text-xs">Nemotron-3 Super (120B)</td>
                <td className="font-mono text-xs text-[var(--text-secondary)]">NVIDIA NIM Cloud API</td>
                <td><span className="badge-semantic badge-success">ACTIVE</span></td>
              </tr>
              <tr>
                <td className="font-mono text-xs text-[var(--primary)] font-semibold">llama3_3_70b_agent</td>
                <td className="font-bold text-xs">Llama 3.3 70B Instruct</td>
                <td className="font-mono text-xs text-[var(--text-secondary)]">NVIDIA NIM Cloud API</td>
                <td><span className="badge-semantic badge-success">ACTIVE</span></td>
              </tr>
              <tr>
                <td className="font-mono text-xs text-[var(--primary)] font-semibold">deepseek_flash_agent</td>
                <td className="font-bold text-xs">DeepSeek Flash 2.5</td>
                <td className="font-mono text-xs text-[var(--text-secondary)]">NVIDIA NIM Cloud API</td>
                <td><span className="badge-semantic badge-success">ACTIVE</span></td>
              </tr>
              <tr>
                <td className="font-mono text-xs text-[var(--primary)] font-semibold">ollama_local_agent</td>
                <td className="font-bold text-xs">Ollama Local Agent</td>
                <td className="font-mono text-xs text-[var(--text-secondary)]">http://localhost:11434</td>
                <td><span className="badge-semantic badge-neutral">CONFIGURED</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
