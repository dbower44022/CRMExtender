import { Bot } from 'lucide-react'
import { formatTimestamp } from '../../lib/formatTimestamp.ts'
import type { ConversationFullData } from '../../types/api.ts'

interface ConversationSummaryCardProps {
  data: ConversationFullData
}

const AI_STATUS_COLORS: Record<string, string> = {
  open: 'bg-green-50 text-green-700',
  closed: 'bg-surface-100 text-surface-500',
  uncertain: 'bg-amber-50 text-amber-700',
}

export function ConversationSummaryCard({ data }: ConversationSummaryCardProps) {
  if (!data.ai_summary && !data.ai_action_items && !data.ai_topics) return null

  return (
    <div className="rounded-lg border border-surface-200 bg-white">
      <div className="flex items-center justify-between border-b border-surface-200 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Bot size={14} className="text-surface-400" />
          <span className="text-xs font-semibold uppercase text-surface-500">AI Summary</span>
        </div>
        {data.ai_status && (
          <span className={`rounded px-1.5 py-0.5 text-xs capitalize ${AI_STATUS_COLORS[data.ai_status] ?? 'bg-surface-100 text-surface-500'}`}>
            {data.ai_status}
          </span>
        )}
      </div>
      <div className="px-4 py-3 space-y-3">
        {/* Summary text */}
        {data.ai_summary && (
          <div className="whitespace-pre-wrap text-sm leading-relaxed text-surface-700">
            {data.ai_summary}
          </div>
        )}

        {/* Action items */}
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

        {/* Topics */}
        {data.ai_topics && (
          <div>
            <div className="mb-1 text-xs font-medium text-surface-400">Topics</div>
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

        {/* Last analyzed */}
        {data.ai_summarized_at && (
          <div className="text-xs text-surface-400">
            Last analyzed {formatTimestamp(data.ai_summarized_at)}
          </div>
        )}
      </div>
    </div>
  )
}
