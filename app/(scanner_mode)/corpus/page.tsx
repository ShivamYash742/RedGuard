"use client"
import React, { Suspense, useEffect, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { benchmarkDataService, Probe } from '@/lib/scanner_mode/data-service'
import ProbeDrawer from '@/components/scanner_mode/ProbeDrawer'
import { Boxes, Search, FileJson, CheckCircle2, XCircle } from 'lucide-react'

function CorpusContent() {
  const searchParams = useSearchParams()
  const allProbes: Probe[] = benchmarkDataService.getAllProbes()
  const families = benchmarkDataService.getAttackFamilies()
  const scenarios = benchmarkDataService.getScenarios()

  const [searchQuery, setSearchQuery] = useState('')
  const [familyFilter, setFamilyFilter] = useState(searchParams.get('family') || 'all')
  const [scenarioFilter, setScenarioFilter] = useState(searchParams.get('scenario') || 'all')
  const [difficultyFilter, setDifficultyFilter] = useState('all')
  const [selectedProbe, setSelectedProbe] = useState<Probe | null>(null)
  const [validation, setValidation] = useState<{ valid: boolean; total: number | null; schemaVersion: string; error: string | null } | null>(null)

  useEffect(() => {
    fetch('/api/probes/validation').then(r => r.json()).then(setValidation).catch(() => setValidation(null))
  }, [])

  const filteredProbes = allProbes.filter(p => {
    const q = searchQuery.toLowerCase()
    const matchesSearch =
      p.id.toLowerCase().includes(q) ||
      p.title.toLowerCase().includes(q) ||
      p.prompt.toLowerCase().includes(q)
    const matchesFamily = familyFilter === 'all' || p.attack_family.toLowerCase() === familyFilter.toLowerCase()
    const matchesScenario = scenarioFilter === 'all' || p.scenario.toLowerCase() === scenarioFilter.toLowerCase()
    const matchesDifficulty = difficultyFilter === 'all' || p.difficulty.toLowerCase() === difficultyFilter.toLowerCase()
    return matchesSearch && matchesFamily && matchesScenario && matchesDifficulty
  })

  const hasFilters = searchQuery || familyFilter !== 'all' || scenarioFilter !== 'all' || difficultyFilter !== 'all'

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="border-b border-[var(--border-subtle)] pb-4">
        <div className="flex items-center gap-2 text-xs font-semibold text-[var(--primary)] uppercase tracking-wider mb-1">
          <Boxes className="h-4 w-4" /> Test Corpus
        </div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-tight">Corpus</h1>
        <p className="text-xs text-[var(--text-secondary)] mt-0.5">
          {allProbes.length} adversarial probes across {families.length} attack families and {scenarios.length} application scenarios — one auditable dataset, filterable by any facet below.
        </p>
      </div>

      {/* Overview strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="research-card">
          <span className="text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider block">Probes</span>
          <div className="text-2xl font-black font-mono text-[var(--text-primary)] mt-1">{allProbes.length}</div>
        </div>
        <div className="research-card">
          <span className="text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider block">Attack Families</span>
          <div className="text-2xl font-black font-mono text-[var(--text-primary)] mt-1">{families.length}</div>
        </div>
        <div className="research-card">
          <span className="text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider block">Scenarios</span>
          <div className="text-2xl font-black font-mono text-[var(--text-primary)] mt-1">{scenarios.length}</div>
        </div>
        <div className="research-card">
          <span className="text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider block">Dataset Version</span>
          <div className="text-2xl font-black font-mono text-[var(--primary)] mt-1">4.0.0</div>
        </div>
      </div>

      {/* Family chips — the primary browsing axis */}
      <div className="space-y-2">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)] block">Browse by Attack Family</span>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setFamilyFilter('all')}
            className={`px-3 py-1.5 rounded-[var(--radius)] text-xs font-medium border transition-colors ${familyFilter === 'all'
                ? 'bg-[var(--primary)] text-[var(--primary-foreground)] border-[var(--primary)] font-semibold'
                : 'bg-[var(--surface-raised)] border-[var(--border-subtle)] text-[var(--text-secondary)] hover:border-[var(--border-default)]'
              }`}
          >
            All Families
          </button>
          {families.map(fam => (
            <button
              key={fam.id}
              onClick={() => setFamilyFilter(familyFilter === fam.id ? 'all' : fam.id)}
              title={fam.description}
              className={`group flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius)] text-xs font-medium border transition-colors ${familyFilter === fam.id
                  ? 'bg-[var(--primary)] text-[var(--primary-foreground)] border-[var(--primary)] font-semibold'
                  : 'bg-[var(--surface-raised)] border-[var(--border-subtle)] text-[var(--text-secondary)] hover:border-[var(--border-default)] hover:text-[var(--text-primary)]'
                }`}
            >
              {fam.name}
              <span className={`font-mono text-[10px] ${familyFilter === fam.id ? 'opacity-80' : 'text-[var(--text-muted)]'}`}>{fam.probeCount}</span>
              <Link
                href={`/corpus/families/${fam.id}`}
                onClick={e => e.stopPropagation()}
                className={`ml-0.5 hidden group-hover:inline underline underline-offset-2 ${familyFilter === fam.id ? '' : 'text-[var(--primary)]'}`}
              >
                details
              </Link>
            </button>
          ))}
        </div>
      </div>

      {/* Facet toolbar */}
      <div className="research-card space-y-3">
        <div className="flex flex-col md:flex-row items-center gap-3">
          <div className="relative flex-1 w-full">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-[var(--text-muted)]" />
            <input
              type="text"
              placeholder="Filter by Probe ID (RG-DI-001), keywords, or payload..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-base)] text-xs text-[var(--text-primary)] focus:outline-none focus:border-[var(--primary)]"
            />
          </div>

          <select
            value={familyFilter}
            onChange={e => setFamilyFilter(e.target.value)}
            className="w-full md:w-auto rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-base)] px-2.5 py-1.5 text-xs text-[var(--text-primary)] focus:outline-none"
          >
            <option value="all">All Attack Families</option>
            {families.map(f => (
              <option key={f.id} value={f.id}>{f.name}</option>
            ))}
          </select>

          <select
            value={scenarioFilter}
            onChange={e => setScenarioFilter(e.target.value)}
            className="w-full md:w-auto rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-base)] px-2.5 py-1.5 text-xs text-[var(--text-primary)] focus:outline-none"
          >
            <option value="all">All Scenarios</option>
            <option value="generic">Generic (cross-scenario)</option>
            {scenarios.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>

          <select
            value={difficultyFilter}
            onChange={e => setDifficultyFilter(e.target.value)}
            className="w-full md:w-auto rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-base)] px-2.5 py-1.5 text-xs text-[var(--text-primary)] focus:outline-none"
          >
            <option value="all">All Difficulties</option>
            <option value="trivial">Trivial</option>
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
            <option value="expert">Expert</option>
          </select>
        </div>

        <div className="flex items-center justify-between text-xs text-[var(--text-muted)] pt-1">
          <span>Showing <strong className="text-[var(--text-primary)]">{filteredProbes.length}</strong> of {allProbes.length} probes</span>
          {hasFilters && (
            <button
              onClick={() => {
                setSearchQuery('')
                setFamilyFilter('all')
                setScenarioFilter('all')
                setDifficultyFilter('all')
              }}
              className="text-[var(--primary)] hover:underline font-medium"
            >
              Reset Filters
            </button>
          )}
        </div>
      </div>

      {/* Probes table */}
      <div className="overflow-x-auto rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)]">
        <table className="research-table">
          <thead>
            <tr>
              <th>Probe ID</th>
              <th>Probe Title</th>
              <th>Attack Family</th>
              <th>Scenario</th>
              <th>Difficulty</th>
              <th>Affected Layers</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {filteredProbes.map(p => (
              <tr
                key={p.id}
                onClick={() => setSelectedProbe(p)}
                className="cursor-pointer hover:bg-[var(--surface-base)] transition-colors"
              >
                <td className="font-mono text-xs font-semibold text-[var(--primary)]">{p.id} {p.benign_control && <span className="badge-semantic badge-neutral ml-1">control</span>}</td>
                <td className="font-medium text-xs text-[var(--text-primary)]">{p.title}</td>
                <td className="capitalize text-xs text-[var(--text-secondary)]">{p.attack_family.replace(/_/g, ' ')}</td>
                <td className="capitalize text-xs text-[var(--text-secondary)]">{p.scenario.replace(/_/g, ' ')}</td>
                <td>
                  <span className="badge-semantic badge-neutral uppercase text-[9px] font-mono">
                    {p.difficulty}
                  </span>
                </td>
                <td className="font-mono text-[11px] text-[var(--text-muted)]">{(p.affected_layers || []).join(', ')}</td>
                <td>
                  <Link
                    href={`/corpus/probes/${p.id}`}
                    onClick={e => e.stopPropagation()}
                    className="text-xs text-[var(--primary)] font-semibold hover:underline"
                  >
                    View Page
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Dataset provenance */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider flex items-center gap-1.5">
            <FileJson className="h-4 w-4 text-[var(--primary)]" /> Dataset File Inventory
          </h2>
          {validation === null ? (
            <span className="badge-semantic badge-warning" title="The API did not answer, so the corpus was not checked">Schema check unavailable</span>
          ) : validation.valid ? (
            <span className="badge-semantic badge-success">
              <CheckCircle2 className="h-3.5 w-3.5" /> Schema v{validation.schemaVersion} passed ({validation.total} probes)
            </span>
          ) : (
            <span className="badge-semantic badge-danger" title={validation.error ?? ''}>
              <XCircle className="h-3.5 w-3.5" /> Schema v{validation.schemaVersion} failed
            </span>
          )}
        </div>
        <div className="overflow-x-auto rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)]">
          <table className="research-table">
            <thead>
              <tr>
                <th>Dataset JSON Filename</th>
                <th>Attack Family</th>
                <th>Probes</th>
                <th>Threat Model</th>
                <th>Target Layers</th>
              </tr>
            </thead>
            <tbody>
              {families.map(f => (
                <tr key={f.id}>
                  <td className="font-mono text-xs font-semibold text-[var(--primary)]">{f.id}.json</td>
                  <td className="font-bold text-xs capitalize text-[var(--text-primary)]">{f.name}</td>
                  <td className="font-mono text-xs text-center font-semibold">{f.probeCount}</td>
                  <td className="text-xs text-[var(--text-secondary)]">{f.threatModel}</td>
                  <td className="font-mono text-[11px] text-[var(--text-muted)]">{f.affectedLayers.join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <ProbeDrawer probe={selectedProbe} onClose={() => setSelectedProbe(null)} />
    </div>
  )
}

export default function CorpusPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-xs">Loading corpus...</div>}>
      <CorpusContent />
    </Suspense>
  )
}
