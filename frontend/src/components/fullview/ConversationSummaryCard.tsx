import { Bot, Pencil, RefreshCw } from 'lucide-react'
import { formatTimestamp } from '../../lib/formatTimestamp.ts'
import type { ConversationFullData } from '../../types/api.ts'

interface ConversationSummaryCardProps {
  data: ConversationFullData
}

export function ConversationSummaryCard({ data }: ConversationSummaryCardProps) {
  // Suppressed when all AI fields are NULL (PRD Section 9.4)
  if (!data.ai_summary && !data.ai_action_items && !data.ai_topics) return null

  return (
    <div className="rounded-lg border border-blue-200 bg-blue-50">
      {/* Header with source badge and actions */}
      <div className="flex items-center justify-between border-b border-blue-200 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Bot size={14} className="text-blue-500" />
          <span className="text-xs font-semibold uppercase text-surface-500">AI Intelligence</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded bg-blue-100 px-1.5 py-0.5 text-[10px] font-medium text-blue-600">
            AI Generated
          </span>
          <button
            disabled
            className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs text-surface-300"
            title="Edit (coming soon)"
          >
            <Pencil size={11} />
          </button>
          <button
            disabled
            className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs text-surface-300"
            title="Regenerate (coming soon)"
          >
            <RefreshCw size={11} />
          </button>
        </div>
      </div>

      <div className="space-y-3 px-4 py-3">
        {/* Summary text */}
        {data.ai_summary && (
          <div>
            <div className="mb-1 text-xs font-medium text-surface-400">Summary</div>
            <div className="whitespace-pre-wrap text-sm leading-relaxed text-surface-700">
              {data.ai_summary}
            </div>
          </div>
        )}

        {/* Action items — read-only list with assignee names */}
        {data.ai_action_items && (
          <div>
            <div className="mb-1 text-xs font-medium text-surface-400">Action Items</div>
            <ul className="space-y-1">
              {data.ai_action_items.split('\n').filter(Boolean).map((item, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-surface-600">
                  <span className="mt-1 h-3.5 w-3.5 shrink-0 rounded border border-surface-300" />
                  <span>{item.replace(/^[-•*]\s*/, '')}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Key topics — inline tags/chips */}
        {data.ai_topics && (
          <div>
            <div className="mb-1 text-xs font-medium text-surface-400">Key Topics</div>
            <div className="flex flex-wrap gap-1.5">
              {data.ai_topics.split(',').map((t, i) => (
                <span
                  key={i}
                  className="rounded-full bg-surface-100 px-2 py-0.5 text-xs text-surface-600"
                >
                  {t.trim()}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Confidence + last processed */}
        <div className="flex flex-wrap items-center gap-3 text-xs text-surface-400">
          {data.ai_confidence != null && (
            <span>Confidence: {data.ai_confidence.toFixed(2)}</span>
          )}
          {data.ai_summarized_at && (
            <span>Last processed: {formatTimestamp(data.ai_summarized_at)}</span>
          )}
        </div>
      </div>
    </div>
  )
}
