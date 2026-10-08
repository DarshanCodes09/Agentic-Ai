export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <section className={`rounded-lg border border-line bg-white p-5 shadow-soft ${className}`}>{children}</section>;
}

export function CardTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="text-base font-semibold text-ink">{children}</h2>;
}
