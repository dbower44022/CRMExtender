import { useConversationPreview } from '../../api/conversationPreview.ts'
import { CHANNEL_ICONS, CHANNEL_LABELS } from '../../lib/channelIcons.ts'
import { formatPreviewTimestamp } from '../../lib/formatTimestamp.ts'
import { buildParticipantColorMap } from '../../lib/participantColors.ts'
import { ChannelBreakdown } from '../shared/ChannelBreakdown.tsx'
import { useNavigationStore } from '../../stores/navigation.ts'
import { MessageSquare, Paperclip } from 'lucide-react'
import type { ConversationPreviewCommunication } from '../../types/api.ts'
import type { ParticipantColorMap } from '../../lib/participantColors.ts'

interface ConversationPreviewCardProps {
  entityId: string
}

export function ConversationPreviewCard({ entityId }: ConversationPreviewCardProps) {
  const { data, isLoading, error } = useConversationPreview(entityId)
  const setActiveEntityType = useNavigationStore((s) => s.setActiveEntityType)
  const setSelectedRow = useNavigationStore((s) => s.setSelectedRow)

  if (isLoading) return <PreviewSkeleton />
  if (error) {
    return (
      <div className="p-4 text-sm text-red-500">
        Failed to load conversation preview.
      </div>
    )
  }
  if (!data) return null

  const colorMap = buildParticipantColorMap(
    data.participants.map((p) => ({ address: p.address, contact_id: p.contact_id })),
    data.account_owner_email,
  )

  return (
    <div className="flex h-full flex-col">
      {/* Header — 2 lines */}
      <div className="shrink-0 border-b border-surface-200 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <MessageSquare size={14} className="shrink-0 text-surface-400" />
          <span className="truncate text-sm font-semibold text-surface-900">
            {data.title || 'Untitled Conversation'}
          </span>
        </div>
        <div className="mt-1 flex items-center gap-2 text-xs text-surface-400">
          {data.status && (
            <span className="rounded bg-surface-100 px-1.5 py-0.5 capitalize text-surface-500">
              {data.status}
            </span>
          )}
          {data.ai_status && (
            <span className={`rounded px-1.5 py-0.5 capitalize ${
              data.ai_status === 'open' ? 'bg-green-50 text-green-700' :
              data.ai_status === 'closed' ? 'bg-surface-100 text-surface-500' :
              'bg-amber-50 text-amber-700'
            }`}>
              AI: {data.ai_status}
            </span>
          )}
          <span>{data.communication_count} comm{data.communication_count !== 1 ? 's' : ''}</span>
          <ChannelBreakdown breakdown={data.channel_breakdown} className="text-surface-400" />
        </div>
      </div>

      {/* Scrollable timeline — all communications, most-recent-first */}
      <div className="flex-1 overflow-y-auto">
        {data.recent_communications.length === 0 ? (
          <div className="flex items-center justify-center p-8 text-sm text-surface-400">
            No communications yet.
          </div>
        ) : (
          <div className="divide-y divide-surface-100">
            {data.recent_communications.map((c) => (
              <PreviewCommEntry
                key={c.id}
                comm={c}
                colorMap={colorMap}
                onClick={() => {
                  setActiveEntityType('communication')
                  setSelectedRow(c.id, -1)
                }}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function PreviewCommEntry({
  comm,
  colorMap,
  onClick,
}: {
  comm: ConversationPreviewCommunication
  colorMap: ParticipantColorMap
  onClick: () => void
}) {
  const ChannelIcon = CHANNEL_ICONS[comm.channel] ?? CHANNEL_ICONS.email
  const senderLabel = comm.sender_name || comm.sender_address || CHANNEL_LABELS[comm.channel] || comm.channel
  const senderAddr = comm.sender_address || senderLabel
  const circleStyle = colorMap.getCircleStyle(senderAddr)

  // Recipient suffix
  let recipientText: string | null = null
  if (comm.recipient_name) {
    const extra = comm.recipient_count - 1
    recipientText = extra > 0 ? `${comm.recipient_name} +${extra}` : comm.recipient_name
  }

  return (
    <button
      onClick={onClick}
      className="flex w-full items-start gap-2.5 px-3 py-2.5 text-left hover:bg-surface-50"
    >
      {/* Colored circle */}
      <div
        className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[10px] font-medium"
        style={circleStyle}
      >
        {senderLabel.charAt(0).toUpperCase()}
      </div>

      <div className="min-w-0 flex-1">
        {/* Identity line */}
        <div className="flex items-center gap-1.5">
          <ChannelIcon size={12} className="shrink-0 text-surface-400" />
          <span className="truncate text-xs font-medium text-surface-700">
            {senderLabel}
          </span>
          {recipientText && (
            <span className="truncate text-xs text-surface-400">
              → {recipientText}
            </span>
          )}
          <span className="ml-auto shrink-0 text-xs text-surface-400">
            {formatPreviewTimestamp(comm.timestamp)}
          </span>
        </div>

        {/* Content — snippet text only (HTML too expensive for preview list) */}
        {comm.snippet && (
          <div className="mt-0.5 line-clamp-3 text-xs leading-relaxed text-surface-500">
            {comm.snippet}
          </div>
        )}

        {/* Attachment indicator */}
        {comm.attachment_count > 0 && (
          <div className="mt-1 flex items-center gap-1 text-xs text-surface-400">
            <Paperclip size={10} />
            <span>{comm.attachment_count}</span>
          </div>
        )}
      </div>
    </button>
  )
}

function PreviewSkeleton() {
  return (
    <div className="space-y-4 p-4">
      <div className="space-y-1">
        <div className="h-4 w-48 animate-pulse rounded bg-surface-200" />
        <div className="h-3 w-32 animate-pulse rounded bg-surface-200" />
      </div>
      <div className="h-px bg-surface-200" />
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="flex items-start gap-2.5">
            <div className="h-6 w-6 animate-pulse rounded-full bg-surface-200" />
            <div className="flex-1 space-y-1">
              <div className="h-3 w-40 animate-pulse rounded bg-surface-200" />
              <div className="h-3 w-full animate-pulse rounded bg-surface-200" />
              <div className="h-3 w-3/4 animate-pulse rounded bg-surface-200" />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
