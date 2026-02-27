import { MessageSquare } from 'lucide-react'
import { formatTimestamp } from '../../lib/formatTimestamp.ts'
import type { ConversationFullData } from '../../types/api.ts'

interface ConversationIdentityCardProps {
  data: ConversationFullData
}

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-green-50 text-green-700',
  open: 'bg-green-50 text-green-700',
  closed: 'bg-surface-100 text-surface-500',
  archived: 'bg-surface-100 text-surface-400',
}

const AI_STATUS_COLORS: Record<string, string> = {
  open: 'bg-green-50 text-green-700',
  closed: 'bg-surface-100 text-surface-500',
  uncertain: 'bg-amber-50 text-amber-700',
}

export function ConversationIdentityCard({ data }: ConversationIdentityCardProps) {
  const dateRange = [data.first_activity_at, data.last_activity_at]
    .filter(Boolean)
    .map((d) => formatTimestamp(d))

  return (
    <div className="border-b border-surface-200 bg-surface-50 px-5 py-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-surface-600">
          <MessageSquare size={16} className="text-surface-400" />
          <span className="font-medium">Conversation</span>
          {data.status && (
            <span className={`rounded px-1.5 py-0.5 text-xs capitalize ${STATUS_COLORS[data.status] ?? 'bg-surface-100 text-surface-500'}`}>
              {data.status}
            </span>
          )}
          {data.ai_status && (
            <span className={`rounded px-1.5 py-0.5 text-xs capitalize ${AI_STATUS_COLORS[data.ai_status] ?? 'bg-surface-100 text-surface-500'}`}>
              AI: {data.ai_status}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 text-xs text-surface-400">
          <span>{data.communication_count} comm{data.communication_count !== 1 ? 's' : ''}</span>
          <span>{data.participant_count} participant{data.participant_count !== 1 ? 's' : ''}</span>
        </div>
      </div>
      <div className="mt-1">
        <h2 className="text-base font-semibold text-surface-900">
          {data.title || 'Untitled Conversation'}
        </h2>
        {dateRange.length > 0 && (
          <div className="mt-0.5 text-xs text-surface-400">
            {dateRange.length === 2 && dateRange[0] !== dateRange[1]
              ? `${dateRange[0]} — ${dateRange[1]}`
              : dateRange[0]}
          </div>
        )}
      </div>
    </div>
  )
}
