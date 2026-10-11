import { OUTCOME_TIERS, TierCounts } from '@/lib/data-service'

export default function TierBar({ counts, total, height = 'h-3' }: { counts: TierCounts; total: number; height?: string }) {
  return (
    <div className={`${height} w-full flex bg-[var(--surface-base)] rounded-full overflow-hidden border border-[var(--border-subtle)]`}>
      {OUTCOME_TIERS.map(t => (
        <div
          key={t.key}
          title={`${t.label}: ${counts[t.key]}`}
          className="h-full transition-all duration-300 ease-out"
          style={{ width: `${total > 0 ? (counts[t.key] / total) * 100 : 0}%`, background: t.color }}
        />
      ))}
    </div>
  )
}
