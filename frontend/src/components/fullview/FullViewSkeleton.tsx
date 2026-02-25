export function FullViewSkeleton() {
  return (
    <div className="space-y-4 p-6">
      {/* Identity bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="h-4 w-4 animate-pulse rounded bg-surface-200" />
          <div className="h-4 w-20 animate-pulse rounded bg-surface-200" />
          <div className="h-4 w-16 animate-pulse rounded bg-surface-200" />
        </div>
        <div className="h-4 w-32 animate-pulse rounded bg-surface-200" />
      </div>

      <div className="h-px bg-surface-200" />

      {/* Header */}
      <div className="space-y-2">
        <div className="h-5 w-48 animate-pulse rounded bg-surface-200" />
        <div className="h-4 w-64 animate-pulse rounded bg-surface-200" />
      </div>

      {/* Subject */}
      <div className="h-6 w-72 animate-pulse rounded bg-surface-200" />

      <div className="h-px bg-surface-200" />

      {/* Body */}
      <div className="space-y-2">
        <div className="h-4 w-full animate-pulse rounded bg-surface-200" />
        <div className="h-4 w-full animate-pulse rounded bg-surface-200" />
        <div className="h-4 w-3/4 animate-pulse rounded bg-surface-200" />
        <div className="h-4 w-full animate-pulse rounded bg-surface-200" />
        <div className="h-4 w-1/2 animate-pulse rounded bg-surface-200" />
      </div>

      {/* CRM Cards */}
      <div className="mt-6 space-y-3">
        <div className="h-24 animate-pulse rounded-lg bg-surface-100" />
        <div className="h-16 animate-pulse rounded-lg bg-surface-100" />
        <div className="h-12 animate-pulse rounded-lg bg-surface-100" />
      </div>
    </div>
  )
}
