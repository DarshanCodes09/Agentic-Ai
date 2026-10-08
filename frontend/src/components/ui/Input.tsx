import type { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

export function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <label className="block space-y-2">
      <span className="text-sm font-medium text-ink">{label}</span>
      {children}
      {hint ? <span className="block text-xs text-muted">{hint}</span> : null}
    </label>
  );
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className="focus-ring w-full rounded-md border border-line bg-white px-3 py-2.5 text-sm text-ink placeholder:text-muted/60"
      {...props}
    />
  );
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className="focus-ring min-h-28 w-full rounded-md border border-line bg-white px-3 py-2.5 text-sm text-ink placeholder:text-muted/60"
      {...props}
    />
  );
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className="focus-ring w-full rounded-md border border-line bg-white px-3 py-2.5 text-sm" {...props} />;
}
