import { AlertCircle, Loader2 } from "lucide-react";
import { Button } from "./Button";

export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex min-h-48 items-center justify-center gap-3 text-sm text-muted">
      <Loader2 className="h-4 w-4 animate-spin" />
      {label}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-5 text-sm text-red-900">
      <div className="mb-3 flex items-center gap-2 font-medium">
        <AlertCircle className="h-4 w-4" />
        {message}
      </div>
      {onRetry ? (
        <Button variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </div>
  );
}

export function EmptyState({ title, body }: { title: string; body?: string }) {
  return (
    <div className="rounded-lg border border-dashed border-line bg-white/60 p-8 text-center">
      <p className="font-medium text-ink">{title}</p>
      {body ? <p className="mt-2 text-sm text-muted">{body}</p> : null}
    </div>
  );
}
