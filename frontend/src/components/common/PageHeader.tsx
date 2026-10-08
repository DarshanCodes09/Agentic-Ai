export function PageHeader({
  title,
  eyebrow,
  description,
  actions
}: {
  title: string;
  eyebrow?: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-8 flex flex-col gap-4 border-b border-line pb-6 md:flex-row md:items-end md:justify-between">
      <div>
        {eyebrow ? <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-muted">{eyebrow}</p> : null}
        <h1 className="font-display text-4xl text-ink md:text-5xl">{title}</h1>
        {description ? <p className="mt-3 max-w-2xl text-sm leading-6 text-muted">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </div>
  );
}
