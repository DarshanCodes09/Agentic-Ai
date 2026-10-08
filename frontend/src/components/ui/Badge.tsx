const toneMap: Record<string, string> = {
  success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  warning: "border-amber-200 bg-amber-50 text-amber-900",
  danger: "border-red-200 bg-red-50 text-red-800",
  neutral: "border-line bg-stone-50 text-muted"
};

export function Badge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: keyof typeof toneMap }) {
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${toneMap[tone]}`}>
      {children}
    </span>
  );
}

export function statusTone(value?: string): keyof typeof toneMap {
  if (!value) return "neutral";
  if (["APPROVED", "MODIFIED", "EVALUATED", "COMPLETED", "MASTERED", "LOW"].includes(value)) return "success";
  if (["PROCESSING", "PENDING", "DEVELOPING", "MEDIUM", "SUBMITTED"].includes(value)) return "warning";
  if (["FAILED", "NEEDS_IMPROVEMENT", "HIGH", "NOT_DEMONSTRATED"].includes(value)) return "danger";
  return "neutral";
}
