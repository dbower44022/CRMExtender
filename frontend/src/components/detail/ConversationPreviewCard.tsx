import { useConversationPreview } from '../../api/conversationPreview.ts'
import { CHANNEL_ICONS, CHANNEL_LABELS } from '../../lib/channelIcons.ts'
import { formatTimestamp } from '../../lib/formatTimestamp.ts'
import { useNavigationStore } from '../../stores/navigation.ts'
import { MessageSquare, Users, AlertTriangle, Tag, ArrowDownRight, ArrowUpRight } from 'lucide-react'
import type { ConversationPreviewCommunication } from '../../types/api.ts'

interface ConversationPreviewCardProps {
  entityId: string
}

export function ConversationPreviewCard({ entityId }: ConversationPreviewCardProps) {
  const { data, isLoading, error } = useConversationPreview(entityId)
  const setActiveEntityType = useNavigationStore((s) => s.setActiveEntityType)
  const setSelectedRow = useNavigationStore((s) => s.setSelectedRow)

  if (isLoading) {
    return <PreviewSkeleton />
  }

  if (error) {
    return (
      <div className="p-4 text-sm text-red-500">
        Failed to load conversation preview.
      </div>
    )
  }

  if (!data) return null

  const dateRange = [data.first_activity_at, data.last_activity_at]
    .filter(Boolean)
    .map((d) => formatTimestamp(d))
    .join(' — ')

  return (
    <div className="flex h-full flex-col">
      {/* Triage / dismissed banner */}
      {(data.triage_result || data.dismissed) && (
        <div className="flex items-center gap-2 border-b border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-800">
          <AlertTriangle size={14} className="shrink-0" />
          <span className="font-medium capitalize">
            {data.dismissed ? 'Dismissed' : data.triage_result!.replace(/_/g, ' ')}
          </span>
        </div>
      )}

      {/* Header */}
      <div className="flex items-start gap-3 border-b border-surface-200 px-4 py-3">
        <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-100 text-surface-500">
          <MessageSquare size={16} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-2">
            <span className="truncate text-sm font-semibold text-surface-900">
              {data.title || 'Untitled Conversation'}
            </span>
            {data.status && (
              <span className="shrink-0 rounded bg-surface-100 px-1.5 py-0.5 text-xs capitalize text-surface-500">
                {data.status}
              </span>
            )}
          </div>
          {dateRange && (
            <div className="mt-0.5 text-xs text-surface-400">{dateRange}</div>
          )}
          <div className="mt-1 flex items-center gap-3 text-xs text-surface-400">
            <span>{data.communication_count} communication{data.communication_count !== 1 ? 's' : ''}</span>
            <span>{data.participant_count} participant{data.participant_count !== 1 ? 's' : ''}</span>
          </div>
        </div>
      </div>

      {/* AI Summary */}
      {data.ai_summary && (
        <div className="border-b border-surface-200 px-4 py-3">
          <div className="flex items-center gap-1.5 text-xs font-medium text-surface-400">
            {data.ai_status && (
              <span className={`rounded px-1.5 py-0.5 text-xs ${
                data.ai_status === 'open' ? 'bg-green-50 text-green-700' :
                data.ai_status === 'closed' ? 'bg-surface-100 text-surface-500' :
                'bg-amber-50 text-amber-700'
              }`}>
                {data.ai_status}
              </span>
            )}
          </div>
          <p className="mt-1 line-clamp-3 text-sm leading-relaxed text-surface-700">
            {data.ai_summary}
          </p>
        </div>
      )}

      {/* Participants */}
      {data.participants.length > 0 && (
        <div className="border-b border-surface-200 px-4 py-3">
          <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-surface-400">
            <Users size={12} />
            Participants ({data.participants.length})
          </div>
          <div className="space-y-1.5">
            {data.participants.slice(0, 6).map((p, i) => (
              <div key={i} className="flex items-center justify-between text-sm">
                {p.contact_id ? (
                  <button
                    className="truncate font-medium text-primary-600 hover:underline"
                    onClick={() => {
                      setActiveEntityType('contact')
                      setSelectedRow(p.contact_id!, -1)
                    }}
                  >
                    {p.contact_name || p.name || p.address}
                  </button>
                ) : (
                  <span className="truncate text-surface-700">
                    {p.name || p.address}
                  </span>
                )}
                <span className="shrink-0 ml-2 text-xs text-surface-400">
                  {p.communication_count}
                </span>
              </div>
            ))}
            {data.participants.length > 6 && (
              <div className="text-xs text-surface-400">
                +{data.participants.length - 6} more
              </div>
            )}
          </div>
        </div>
      )}

      {/* Recent Communications */}
      {data.recent_communications.length > 0 && (
        <div className="flex-1 overflow-y-auto border-b border-surface-200 px-4 py-3">
          <div className="mb-2 text-xs font-medium text-surface-400">
            Recent Communications
          </div>
          <div className="space-y-2">
            {data.recent_communications.map((c) => (
              <CommEntry
                key={c.id}
                comm={c}
                onClick={() => {
                  setActiveEntityType('communication')
                  setSelectedRow(c.id, -1)
                }}
              />
            ))}
          </div>
        </div>
      )}

      {/* Tags */}
      {data.tags.length > 0 && (
        <div className="px-4 py-3">
          <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-surface-400">
            <Tag size={12} />
            Tags
          </div>
          <div className="flex flex-wrap gap-1.5">
            {data.tags.map((t) => (
              <span
                key={t.id}
                className="rounded-full bg-surface-100 px-2 py-0.5 text-xs text-surface-600"
              >
                {t.name}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function CommEntry({
  comm,
  onClick,
}: {
  comm: ConversationPreviewCommunication
  onClick: () => void
}) {
  const ChannelIcon = CHANNEL_ICONS[comm.channel] ?? CHANNEL_ICONS.email
  const DirectionIcon = comm.direction === 'outbound' ? ArrowUpRight : ArrowDownRight
  const dirColor = comm.direction === 'outbound' ? 'text-blue-400' : 'text-green-400'

  return (
    <button
      onClick={onClick}
      className="flex w-full items-start gap-2 rounded p-1.5 text-left hover:bg-surface-50"
    >
      <ChannelIcon size={14} className="mt-0.5 shrink-0 text-surface-400" />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-1">
          <span className="truncate text-xs font-medium text-surface-700">
            {comm.sender_name || comm.sender_address || CHANNEL_LABELS[comm.channel] || comm.channel}
          </span>
          <span className="shrink-0 text-xs text-surface-400">
            {formatTimestamp(comm.timestamp)}
          </span>
        </div>
        {comm.subject && (
          <div className="truncate text-xs text-surface-500">{comm.subject}</div>
        )}
        {comm.snippet && (
          <div className="mt-0.5 line-clamp-1 text-xs text-surface-400">{comm.snippet}</div>
        )}
      </div>
      <DirectionIcon size={12} className={`mt-0.5 shrink-0 ${dirColor}`} />
    </button>
  )
}

function PreviewSkeleton() {
  return (
    <div className="space-y-4 p-4">
      <div className="flex items-center gap-3">
        <div className="h-8 w-8 animate-pulse rounded-full bg-surface-200" />
        <div className="space-y-1">
          <div className="h-4 w-40 animate-pulse rounded bg-surface-200" />
          <div className="h-3 w-28 animate-pulse rounded bg-surface-200" />
        </div>
      </div>
      <div className="h-px bg-surface-200" />
      <div className="space-y-2">
        <div className="h-4 w-full animate-pulse rounded bg-surface-200" />
        <div className="h-4 w-3/4 animate-pulse rounded bg-surface-200" />
      </div>
      <div className="h-px bg-surface-200" />
      <div className="space-y-2">
        <div className="h-4 w-full animate-pulse rounded bg-surface-200" />
        <div className="h-4 w-full animate-pulse rounded bg-surface-200" />
        <div className="h-4 w-3/4 animate-pulse rounded bg-surface-200" />
      </div>
    </div>
  )
}
