import { MessageSquare, FolderOpen } from 'lucide-react'
import { ChannelBreakdown } from '../shared/ChannelBreakdown.tsx'
import type { ConversationFullData } from '../../types/api.ts'

interface ConversationIdentityCardProps {
  data: ConversationFullData
}

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-green-50 text-green-700',
  open: 'bg-green-50 text-green-700',
  stale: 'bg-amber-50 text-amber-700',
  closed: 'bg-surface-100 text-surface-500',
  archived: 'bg-surface-100 text-surface-400',
}

const AI_STATUS_COLORS: Record<string, string> = {
  open: 'bg-green-50 text-green-700',
  closed: 'bg-surface-100 text-surface-500',
  uncertain: 'bg-amber-50 text-amber-700',
}

export function ConversationIdentityCard({ data }: ConversationIdentityCardProps) {
  const TypeIcon = data.is_aggregate ? FolderOpen : MessageSquare
  const channelCount = Object.keys(data.channel_breakdown).length

  return (
    <div className="shrink-0 border-b border-surface-200 bg-surface-50 px-5 py-3">
      {/* Line 1: Type icon + Subject */}
      <div className="flex items-center gap-2">
        <TypeIcon size={16} className="shrink-0 text-surface-400" />
        <h2 className="truncate text-base font-semibold text-surface-900">
          {data.title || 'Untitled Conversation'}
        </h2>
      </div>

      {/* Line 2: Statuses + counts + channel breakdown */}
      <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-surface-400">
        {data.status && (
          <span className={`rounded px-1.5 py-0.5 capitalize ${STATUS_COLORS[data.status] ?? 'bg-surface-100 text-surface-500'}`}>
            {data.status}
          </span>
        )}
        {data.ai_status && (
          <span className={`rounded px-1.5 py-0.5 capitalize ${AI_STATUS_COLORS[data.ai_status] ?? 'bg-surface-100 text-surface-500'}`}>
            AI: {data.ai_status}
          </span>
        )}
        {data.is_aggregate && data.children.length > 0 && (
          <span>{data.children.length} conversation{data.children.length !== 1 ? 's' : ''}</span>
        )}
        <span>{data.communication_count} communication{data.communication_count !== 1 ? 's' : ''}</span>
        {/* Channel breakdown — suppressed for single-channel conversations */}
        {channelCount > 1 && (
          <ChannelBreakdown breakdown={data.channel_breakdown} />
        )}
      </div>

      {/* Line 3: Optional description (lighter text) */}
      {data.description && (
        <div className="mt-1 text-xs text-surface-400">
          {data.description}
        </div>
      )}
    </div>
  )
}
