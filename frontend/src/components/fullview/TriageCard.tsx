import { AlertTriangle } from 'lucide-react'

interface TriageCardProps {
  triageResult: string
  triageReason: string | null
}

export function TriageCard({ triageResult, triageReason }: TriageCardProps) {
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50">
      <div className="flex items-center gap-2 border-b border-amber-200 px-4 py-2.5">
        <AlertTriangle size={14} className="text-amber-600" />
        <span className="text-xs font-semibold uppercase text-amber-700">Filtered by Triage</span>
      </div>
      <div className="px-4 py-3">
        <div className="text-sm text-amber-800">
          <span className="font-medium">Classification:</span>{' '}
          <span className="capitalize">{triageResult.replace(/_/g, ' ')}</span>
        </div>
        {triageReason && (
          <div className="mt-1 text-sm text-amber-700">
            <span className="font-medium">Reason:</span> {triageReason}
          </div>
        )}
        <div className="mt-3">
          <button
            className="rounded bg-amber-100 px-3 py-1.5 text-xs font-medium text-amber-800 hover:bg-amber-200 disabled:opacity-40"
            disabled
            title="Override triage (coming soon)"
          >
            Override — Mark as Real
          </button>
        </div>
      </div>
    </div>
  )
}
