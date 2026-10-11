"use client"
import React, { use, useEffect, useState } from 'react'
import Link from 'next/link'
import { AlertTriangle, ArrowLeft, ChevronDown, Download, FileText } from 'lucide-react'
import {
  labService, ExperimentReport, ObjectiveLevel, armName, formatDuration, formatRate,
  FAMILY_LABELS, IMPACT_LABELS, MECHANISM_LABELS, OBJECTIVE_LABELS, OUTCOME_LABELS,
} from '@/lib/lab-service'
import { FINISH_REASONS } from '@/components/AgentCards'
import { ObjectiveGlyph } from '@/components/LabRoute'
import { TableSkeleton } from '@/components/Skeletons'

const section = 'overflow-hidden rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-raised)]'
const heading = 'border-b border-[var(--border-subtle)] px-4 py-3 text-base font-semibold text-[var(--text-primary)]'
const th = 'px-3 py-2 text-left text-xs font-semibold text-[var(--text-secondary)] whitespace-nowrap'
const td = 'px-3 py-2 align-top text-sm text-[var(--text-primary)]'
const num = 'font-mono tabular-nums'
const button = 'inline-flex items-center gap-1.5 rounded-[var(--radius)] border border-[var(--border-default)] bg-[var(--surface-raised)] px-3 py-2 text-sm font-semibold text-[var(--text-primary)] hover:border-[var(--text-secondary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--primary)]'

/** `CONTAINED_AT_B` → `sealed at B`, as the experiment page says it. */
const stopLabel = (label: string | null) =>
  !label ? '—' : label.startsWith('CONTAINED_AT_') ? `sealed at ${label.slice(13)}` : label === 'NOT_CONTAINED' ? 'not contained' : 'entry-local'

const ms = (value: number | null | undefined) => (value === null || value === undefined ? '—' : formatDuration(value))

function counts(record: Record<string, number>, labels?: Record<string, string>): string {
  const entries = Object.entries(record).sort((a, b) => b[1] - a[1])
  return entries.length ? entries.map(([k, v]) => `${labels?.[k] ?? k} ${v}`).join(', ') : '—'
}

function Table({ head, children }: { head: string[]; children: React.ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <thead className="border-b border-[var(--border-subtle)] bg-[var(--surface-base)]">
          <tr>{head.map((h) => <th key={h} scope="col" className={th}>{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-[var(--border-subtle)]">{children}</tbody>
      </table>
    </div>
  )
}

function Facts({ children }: { children: React.ReactNode }) {
  return <dl className="grid grid-cols-[minmax(8rem,auto)_1fr] gap-x-4 gap-y-2 px-4 py-3 text-sm">{children}</dl>
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <>
      <dt className="text-[var(--text-secondary)]">{label}</dt>
      <dd className="min-w-0 break-words text-[var(--text-primary)]">{children}</dd>
    </>
  )
}

export default function LabReportPage({ params }: { params: Promise<{ experimentId: string }> }) {
  const { experimentId } = use(params)
  const [report, setReport] = useState<ExperimentReport | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    labService.fetchReport(experimentId).then(setReport).catch((err) => setError(String(err)))
  }, [experimentId])

  if (error) {
    return (
      <div className="space-y-4">
        <BackLink id={experimentId} />
        <div role="alert" className="flex items-start gap-2 rounded-[var(--radius)] border border-[var(--danger)]/30 bg-[var(--danger-bg)] p-3 text-sm text-[var(--text-primary)]">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--danger)]" /><span className="break-words">{error}</span>
        </div>
      </div>
    )
  }
  if (!report) return <TableSkeleton />

  const { experiment: exp, execution: ex, suitability: suit, results: res } = report
  const agg = res.aggregate
  const versions = exp.versions
  const evidenceGroups = groupEvidence(report.runs)

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 border-b border-[var(--border-subtle)] pb-5 md:flex-row md:items-end md:justify-between">
        <div className="min-w-0">
          <BackLink id={experimentId} />
          <h1 className="mt-2 text-2xl font-bold tracking-tight text-[var(--text-primary)]">Report · {exp.name}</h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            <span className="font-semibold text-[var(--text-primary)]">{armName(exp.arm)}</span>
            {' · '}{exp.scripted ? 'scripted replay, no model' : <span className="font-mono">{exp.provider} / {exp.model}</span>}
            {' · '}{report.running ? 'still running' : report.complete ? 'complete' : 'incomplete'}
            {' · '}generated {new Date(report.generated_at).toLocaleString()}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <a href={labService.reportUrl(experimentId, 'md')} download={`redguard-lab-${experimentId}.md`} className={button}>
            <FileText className="h-3.5 w-3.5" /> Markdown
          </a>
          <a href={labService.reportUrl(experimentId, 'json')} download={`redguard-lab-${experimentId}.json`} className={button}>
            <Download className="h-3.5 w-3.5" /> JSON
          </a>
        </div>
      </header>

      {(report.running || !report.complete) && (
        <div role="status" className="flex items-start gap-2 rounded-[var(--radius)] border border-[var(--warning)]/40 bg-[var(--warning-bg)] p-3 text-sm text-[var(--text-primary)]">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--warning)]" />
          <span>{report.running ? 'The experiment is still running; this report covers what has finished so far.' : `Only ${ex.pairs_completed} of ${ex.pairs_planned} pairs completed. Resume the experiment to finish it.`}</span>
        </div>
      )}

      <section aria-label="Summary" className={section}>
        <h2 className={heading}>Summary</h2>
        <ul className="list-disc space-y-1.5 py-3 pl-9 pr-4 text-sm text-[var(--text-primary)]">
          {report.findings.map((f) => <li key={f}>{f}</li>)}
        </ul>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section aria-label="Setup" className={section}>
          <h2 className={heading}>Setup</h2>
          <Facts>
            <Fact label="Defence"><span className="font-semibold">{armName(exp.arm)}</span> <span className="text-[var(--text-secondary)]">· {exp.arm_description}</span></Fact>
            <Fact label="Model">{exp.scripted ? 'scripted replay (no model)' : <span className="font-mono">{exp.provider} / {exp.model} · temperature {exp.temperature ?? '—'}</span>}</Fact>
            <Fact label="Step budget">{`${exp.max_steps} per agent`}</Fact>
            <Fact label="Cases">{`${exp.cases.length} × ${exp.repetitions} repetitions`}</Fact>
            <Fact label="Created">{new Date(exp.created_at).toLocaleString()}</Fact>
            <Fact label="Git commit"><span className="font-mono text-xs">{versions.git_commit?.slice(0, 12) ?? 'unknown'}{versions.git_clean === false && ' (uncommitted changes)'}</span></Fact>
            <Fact label="Versions"><span className="font-mono text-xs">{Object.entries(versions.versions ?? {}).map(([k, v]) => `${k.replace('_version', '')} ${v}`).join(' · ')}</span></Fact>
          </Facts>
        </section>
        <section aria-label="Execution" className={section}>
          <h2 className={heading}>Execution</h2>
          <Facts>
            <Fact label="Pairs"><span className={num}>{ex.pairs_completed}</span> of {ex.pairs_planned} completed{ex.pairs_failed > 0 && <> · <span className={num}>{ex.pairs_failed}</span> failed</>}{ex.pairs_not_finished > 0 && <> · <span className={num}>{ex.pairs_not_finished}</span> not finished</>}</Fact>
            <Fact label="Runs recorded">{`${ex.runs_recorded} (${counts(ex.run_status)})`}</Fact>
            <Fact label="Total run time">{ms(ex.total_run_time_ms)}</Fact>
            <Fact label="Mean run">{ms(ex.mean_run_time_ms)}</Fact>
            <Fact label="Mean model call">{exp.scripted ? 'n/a (scripted)' : ms(ex.mean_model_latency_ms)}</Fact>
            <Fact label="Suitability">{suit.applies
              ? <span className={suit.suitable === false ? 'font-semibold text-[var(--warning)]' : ''}>
                  {formatRate(suit.invalid_rate)} invalid replies ({suit.invalid_replies} of {suit.steps} steps), gate {formatRate(suit.gate, 0)} · {suit.suitable === false ? 'unsuitable' : suit.suitable ? 'suitable' : 'no steps yet'}
                </span>
              : 'n/a (scripted)'}</Fact>
            <Fact label="Agent turns ended">{counts(suit.agent_endings, FINISH_REASONS)}</Fact>
          </Facts>
        </section>
      </div>

      <section aria-label="Results" className={section}>
        <h2 className={heading}>Results <span className="font-normal text-[var(--text-secondary)]">· {res.n_attack_runs} valid attack runs{res.n_failed_pairs > 0 && `, ${res.n_failed_pairs} pairs excluded`}</span></h2>
        <Table head={['Measure', 'Rate', '95% interval', 'Per-case mean']}>
          {([['Entry agent compromised (ICR)', 'icr'], ['Objective reached (ASR)', 'asr'], ['Objective partially reached', 'partial_rate']] as const).map(([label, key]) => {
            const block = agg[key]
            return (
              <tr key={key}>
                <td className={td}>{label}</td>
                <td className={`${td} ${num}`}>{formatRate(block?.value)}</td>
                <td className={`${td} ${num}`}>{block?.ci ? `${formatRate(block.ci[0])} – ${formatRate(block.ci[1])}` : '—'}</td>
                <td className={`${td} ${num}`}>{formatRate(res.macro[key])}</td>
              </tr>
            )
          })}
          <tr>
            <td className={td}>Propagated past a compromised entry (CPR)</td>
            <td className={`${td} ${num}`}>{formatRate(agg.cpr)}</td>
            <td className={`${td} text-[var(--text-secondary)]`}>over {agg.cpr_denominator_size ?? 0} runs</td>
            <td className={td}>—</td>
          </tr>
          <tr>
            <td className={td}>Contained, of runs with a compromised entry</td>
            <td className={`${td} ${num}`}>{formatRate(agg.containment_rate)}</td>
            <td className={td}>—</td>
            <td className={td}>—</td>
          </tr>
        </Table>
      </section>

      <section aria-label="Where attacks stopped" className={section}>
        <h2 className={heading}>Where attacks stopped</h2>
        {report.containment.length ? (
          <>
            <Table head={['Stopped at', 'Mechanism', 'Runs']}>
              {report.containment.map((c) => (
                <tr key={`${c.status}-${c.agent}-${c.mechanism}`}>
                  <td className={td}>{c.status === 'CONTAINED' ? `Agent ${c.agent}` : c.status === 'NOT_CONTAINED' ? 'Not contained' : 'Entry-local'}</td>
                  <td className={td}>{c.mechanism ? MECHANISM_LABELS[c.mechanism] ?? c.mechanism : '—'}</td>
                  <td className={`${td} ${num}`}>{c.runs}</td>
                </tr>
              ))}
            </Table>
            <p className="border-t border-[var(--border-subtle)] px-4 py-2 text-xs text-[var(--text-secondary)]">
              Over all {res.n_attack_runs} valid attack runs. The containment rate above counts only runs whose entry agent was compromised ({agg.cpr_denominator_size ?? 0} here).
            </p>
          </>
        ) : <p className="px-4 py-3 text-sm text-[var(--text-secondary)]">No valid attack runs yet.</p>}
      </section>

      <section aria-label="Agents" className={section}>
        <h2 className={heading}>Agents</h2>
        <Table head={['Agent', 'Compromised', 'Influenced', 'Not influenced', 'Steps attack / clean', 'Actions', 'Tools', 'Refused', 'Invalid replies', 'Turns ended', 'Mean model call']}>
          {Object.entries(report.agents).map(([agent, a]) => (
            <tr key={agent}>
              <td className={`${td} font-bold`}>{agent}</td>
              <td className={`${td} ${num}`}>{a.impact.COMPROMISED}</td>
              <td className={`${td} ${num}`}>{a.impact.INFLUENCED}</td>
              <td className={`${td} ${num}`}>{a.impact.NOT_INFLUENCED}</td>
              <td className={`${td} ${num}`}>{a.steps.attack} / {a.steps.clean}</td>
              <td className={`${td} font-mono text-xs`}>{counts(a.actions)}</td>
              <td className={`${td} font-mono text-xs`}>{counts(a.tools)}</td>
              <td className={`${td} font-mono text-xs`}>{counts(a.refused)}</td>
              <td className={`${td} ${num} ${a.invalid_replies ? 'text-[var(--warning)]' : ''}`}>{a.invalid_replies}</td>
              <td className={`${td} text-xs`}>{counts(a.endings, FINISH_REASONS)}</td>
              <td className={`${td} ${num}`}>{exp.scripted ? '—' : ms(a.mean_latency_ms)}</td>
            </tr>
          ))}
        </Table>
      </section>

      <section aria-label="Cases" className={section}>
        <h2 className={heading}>Cases</h2>
        <Table head={['Case', 'Attack', 'n', 'ICR', 'ASR', 'Partial', 'CPR', 'SOC', 'Objectives', 'Stopped', 'Drift attack / null']}>
          {report.cases.map((c) => (
            <tr key={c.id}>
              <td className={td}><span className="font-mono font-bold">{c.id}</span><span className="block text-xs text-[var(--text-secondary)]">{c.title}</span></td>
              <td className={`${td} text-xs`}>{FAMILY_LABELS[c.family ?? ''] ?? c.family} · {c.channel} at {c.injection_point}</td>
              <td className={`${td} ${num}`}>{c.n}</td>
              <td className={`${td} ${num}`}>{formatRate(c.icr)}</td>
              <td className={`${td} ${num}`}>{formatRate(c.asr)}</td>
              <td className={`${td} ${num}`}>{formatRate(c.partial_rate)}</td>
              <td className={`${td} ${num}`}>{formatRate(c.cpr)}</td>
              <td className={`${td} ${num}`}>{formatRate(c.soc)}</td>
              <td className={`${td} text-xs`}>{counts(c.objectives, OBJECTIVE_LABELS)}</td>
              <td className={`${td} text-xs`}>{counts(Object.fromEntries(Object.entries(c.stopped_at).map(([k, v]) => [stopLabel(k), v])))}</td>
              <td className={`${td} ${num} text-xs`}>{c.drift?.attack == null ? '—' : `${c.drift.attack.toFixed(3)} / ${c.drift.null == null ? 'no null' : c.drift.null.toFixed(3)}`}</td>
            </tr>
          ))}
        </Table>
      </section>

      <section aria-label="Runs" className={section}>
        <h2 className={heading}>Runs</h2>
        <Table head={['Case', 'Rep', 'Objective', 'Containment', 'Outcome', 'Agent impact', 'Attack run', 'Clean run', '']}>
          {report.runs.map((r) => (
            <tr key={r.pair_id}>
              <td className={`${td} whitespace-nowrap font-mono`}>{r.case_id}</td>
              <td className={`${td} ${num}`}>{r.repetition}</td>
              <td className={td}>
                {r.objective
                  ? <span className="inline-flex items-center gap-1.5 whitespace-nowrap"><ObjectiveGlyph level={r.objective as ObjectiveLevel} />{OBJECTIVE_LABELS[r.objective]}</span>
                  : <span className="text-[var(--text-secondary)]">{r.status?.toLowerCase() ?? '—'}</span>}
              </td>
              <td className={`${td} whitespace-nowrap`}>{r.containment_status === 'CONTAINED' ? `Sealed at ${r.containment_agent}` : r.containment_status === 'NOT_CONTAINED' ? 'Not contained' : r.containment_status ? 'Entry-local' : '—'}</td>
              <td className={`${td} text-xs`}>{r.system_outcome ? OUTCOME_LABELS[r.system_outcome] : r.invalid_reason ?? '—'}</td>
              <td className={`${td} text-xs`}>{Object.entries(r.agent_impact).map(([a, l]) => `${a} ${IMPACT_LABELS[l]}`).join(', ') || '—'}</td>
              <td className={`${td} text-xs ${num}`}>{r.attack ? `${r.attack.steps} steps · ${ms(r.attack.duration_ms)} · ${r.attack.refused} refused` : '—'}</td>
              <td className={`${td} text-xs ${num}`}>{r.clean ? `${r.clean.steps} steps · ${ms(r.clean.duration_ms)}` : '—'}</td>
              <td className={td}>{r.attack_run_id && <Link href={`/lab/runs/${r.attack_run_id}`} className="text-sm font-semibold text-[var(--primary)] hover:underline">Replay</Link>}</td>
            </tr>
          ))}
        </Table>
      </section>

      {evidenceGroups.length > 0 && (
        <section aria-label="Evidence" className={section}>
          <h2 className={heading}>Evidence</h2>
          <p className="px-4 pt-3 text-xs text-[var(--text-secondary)]">
            Per attack run: the trace events its verdict cites, then the attack trail, every action that descends from the planted artifact. Repetitions with an identical trace are listed once.
          </p>
          <div className="space-y-2 p-4">
            {evidenceGroups.map((g) => (
              <details key={g.key} className="group rounded-[var(--radius)] border border-[var(--border-subtle)]">
                <summary className="flex cursor-pointer list-none items-center gap-1.5 px-3 py-2 text-sm text-[var(--text-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--primary)] [&::-webkit-details-marker]:hidden">
                  <ChevronDown className="h-4 w-4 shrink-0 -rotate-90 transition-transform group-open:rotate-0 motion-reduce:transition-none" aria-hidden />
                  <span className="font-mono font-bold">{g.caseId}</span>
                  <span className="text-[var(--text-secondary)]">rep {g.reps.join(', ')} · {g.objective ? OBJECTIVE_LABELS[g.objective] : 'no verdict'} · {stopLabel(g.containment)}</span>
                </summary>
                <ol className="space-y-1 border-t border-[var(--border-subtle)] px-3 py-2 font-mono text-xs">
                  {g.evidence.map((line) => <li key={`c-${line}`} className="text-[var(--text-primary)]"><span className="text-[var(--text-secondary)]">cited </span>{line}</li>)}
                  {g.trail.map((line) => <li key={`t-${line}`} className={line.includes('refused') ? 'text-[var(--success)]' : 'text-[var(--text-primary)]'}><span className="text-[var(--text-secondary)]">trail </span>{line}</li>)}
                  {g.more > 0 && <li className="text-[var(--text-secondary)]">… {g.more} more in the replay</li>}
                </ol>
              </details>
            ))}
          </div>
        </section>
      )}

      <section aria-label="Caveats" className={section}>
        <h2 className={heading}>Caveats</h2>
        <ul className="list-disc space-y-1.5 py-3 pl-9 pr-4 text-sm text-[var(--text-secondary)]">
          {report.caveats.map((c) => <li key={c}>{c}</li>)}
        </ul>
      </section>
    </div>
  )
}

function groupEvidence(runs: ExperimentReport['runs']) {
  const groups = new Map<string, { key: string; caseId: string; reps: number[]; objective: ObjectiveLevel | null; containment: string | null; evidence: string[]; trail: string[]; more: number }>()
  for (const r of runs) {
    if (!r.evidence.length && !r.attack_trail.length) continue
    const key = JSON.stringify([r.case_id, r.objective, r.containment, r.evidence, r.attack_trail])
    const group = groups.get(key)
    if (group) group.reps.push(r.repetition)
    else groups.set(key, {
      key, caseId: r.case_id, reps: [r.repetition], objective: r.objective, containment: r.containment,
      evidence: r.evidence, trail: r.attack_trail, more: r.attack_trail_total - r.attack_trail.length,
    })
  }
  return [...groups.values()]
}

function BackLink({ id }: { id: string }) {
  return (
    <Link href={`/lab/experiments/${id}`} className="inline-flex items-center gap-1 text-sm font-semibold text-[var(--primary)] hover:underline">
      <ArrowLeft className="h-3.5 w-3.5" /> Experiment
    </Link>
  )
}
