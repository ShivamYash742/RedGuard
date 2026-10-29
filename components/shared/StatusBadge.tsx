/** A run's status as the stored string has it: COMPLETED, RUNNING, or "FAILED: <reason>" (up to 200 characters). */
export default function StatusBadge({ status }: { status: string }) {
  const failed = status.startsWith('FAILED')
  const tone = status === 'COMPLETED' ? 'badge-success' : failed ? 'badge-danger' : 'badge-neutral'
  const shown = failed ? 'FAILED' : status
  return <span className={`badge-semantic ${tone}`} title={failed ? status : undefined}>{shown}</span>
}
