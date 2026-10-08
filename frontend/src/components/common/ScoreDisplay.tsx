export function ScoreDisplay({ value, max, label }: { value: number; max?: number; label?: string }) {
  const percent = max ? Math.round((value / max) * 100) : Math.round(value);
  return (
    <div>
      {label ? <p className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</p> : null}
      <div className="mt-1 flex items-end gap-2">
        <span className="font-display text-5xl text-ink">{max ? value.toFixed(1) : percent}</span>
        <span className="mb-2 text-sm text-muted">{max ? `/ ${max}` : "%"}</span>
      </div>
      <div className="mt-3 h-2 rounded-full bg-stone-100">
        <div className="h-2 rounded-full bg-ink" style={{ width: `${Math.max(0, Math.min(100, percent))}%` }} />
      </div>
    </div>
  );
}
