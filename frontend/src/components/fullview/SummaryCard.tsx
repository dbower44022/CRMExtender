import { Bot, Pencil, RefreshCw } from 'lucide-react'
import type { CommunicationFullData } from '../../types/api.ts'

interface SummaryCardProps {
  data: CommunicationFullData
}

export function SummaryCard({ data }: SummaryCardProps) {
  if (!data.ai_summary) return null

  return (
    <div className="rounded-lg border border-blue-200 bg-blue-50">
      <div className="flex items-center justify-between border-b border-blue-200 px-4 py-2.5">
        <span className="text-xs font-semibold uppercase text-surface-500">Summary</span>
        <div className="flex items-center gap-2">
          {data.ai_summarized_at && (
            <span className="flex items-center gap-1 rounded bg-surface-100 px-1.5 py-0.5 text-xs text-surface-500">
              <Bot size={10} />
              AI Generated
            </span>
          )}
          <button
            className="rounded p-1 text-surface-400 hover:bg-surface-100 disabled:opacity-40"
            disabled
            title="Edit summary (coming soon)"
          >
            <Pencil size={12} />
          </button>
          <button
            className="rounded p-1 text-surface-400 hover:bg-surface-100 disabled:opacity-40"
            disabled
            title="Regenerate summary (coming soon)"
          >
            <RefreshCw size={12} />
          </button>
        </div>
      </div>
      <div className="px-4 py-3">
        <div className="whitespace-pre-wrap text-sm leading-relaxed text-surface-700">
          {data.ai_summary}
        </div>
      </div>
    </div>
  )
}
