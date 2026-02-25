import { useCommunicationPreview } from '../../api/communicationPreview.ts'
import { CHANNEL_ICONS, CHANNEL_LABELS } from '../../lib/channelIcons.ts'
import { formatTimestamp } from '../../lib/formatTimestamp.ts'
import { sanitizeHtml } from '../../lib/sanitizeHtml.ts'
import { Paperclip, AlertTriangle } from 'lucide-react'
import type { CommunicationParticipant } from '../../types/api.ts'

interface CommunicationPreviewCardProps {
  entityId: string
}

export function CommunicationPreviewCard({ entityId }: CommunicationPreviewCardProps) {
  const { data, isLoading, error } = useCommunicationPreview(entityId)

  if (isLoading) {
    return <PreviewSkeleton />
  }

  if (error) {
    return (
      <div className="p-4 text-sm text-red-500">
        Failed to load communication preview.
      </div>
    )
  }

  if (!data) return null

  const ChannelIcon = CHANNEL_ICONS[data.channel] ?? CHANNEL_ICONS.email
  const channelLabel = CHANNEL_LABELS[data.channel] ?? data.channel
  const isEmailLike = data.channel === 'email'
  const isPhoneLike = data.channel === 'phone' || data.channel === 'phone_manual' ||
                      data.channel === 'video' || data.channel === 'video_manual'

  return (
    <div className="flex h-full flex-col">
      {/* Triage banner */}
      {data.triage_result && (
        <div className="flex items-center gap-2 border-b border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-800">
          <AlertTriangle size={14} className="shrink-0" />
          <span className="font-medium capitalize">{data.triage_result.replace(/_/g, ' ')}</span>
        </div>
      )}

      {/* Header: channel icon + sender + timestamp */}
      <div className="flex items-start gap-3 border-b border-surface-200 px-4 py-3">
        <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-100 text-surface-500">
          <ChannelIcon size={16} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-2">
            <span className="truncate text-sm font-semibold text-surface-900">
              {data.sender_name || data.sender_address || channelLabel}
            </span>
            <span className="shrink-0 text-xs text-surface-400">
              {formatTimestamp(data.timestamp)}
            </span>
          </div>
          {data.sender_name && data.sender_address && (
            <div className="truncate text-xs text-surface-400">
              {data.sender_address}
            </div>
          )}
        </div>
      </div>

      {/* Recipients (email only) */}
      {isEmailLike && (data.participants.to.length > 0 || data.participants.cc.length > 0) && (
        <div className="space-y-0.5 border-b border-surface-200 px-4 py-2 text-xs text-surface-500">
          {data.participants.to.length > 0 && (
            <div className="flex gap-1">
              <span className="shrink-0 font-medium text-surface-400">To:</span>
              <span className="truncate">{formatParticipants(data.participants.to)}</span>
            </div>
          )}
          {data.participants.cc.length > 0 && (
            <div className="flex gap-1">
              <span className="shrink-0 font-medium text-surface-400">Cc:</span>
              <span className="truncate">{formatParticipants(data.participants.cc)}</span>
            </div>
          )}
        </div>
      )}

      {/* Subject */}
      {data.subject && (
        <div className="border-b border-surface-200 px-4 py-2">
          <h3 className="text-sm font-semibold text-surface-900">{data.subject}</h3>
        </div>
      )}

      {/* Duration (phone/video only) */}
      {isPhoneLike && data.duration_seconds != null && (
        <div className="border-b border-surface-200 px-4 py-2 text-xs text-surface-500">
          Duration: {formatDuration(data.duration_seconds)}
          {data.phone_number_from && (
            <span className="ml-3">From: {data.phone_number_from}</span>
          )}
          {data.phone_number_to && (
            <span className="ml-3">To: {data.phone_number_to}</span>
          )}
        </div>
      )}

      {/* Attachments */}
      {data.attachments.length > 0 && (
        <div className="flex items-center gap-2 border-b border-surface-200 px-4 py-2 text-xs text-surface-500">
          <Paperclip size={12} className="shrink-0" />
          <span className="truncate">
            {data.attachments.map(a => a.filename).join(', ')}
          </span>
        </div>
      )}

      {/* Body */}
      {isEmailLike && data.cleaned_html ? (
        <HtmlBody html={data.cleaned_html} />
      ) : (
        <div className="flex-1 overflow-y-auto px-4 py-3">
          {data.search_text ? (
            <div className="whitespace-pre-wrap text-sm leading-relaxed text-surface-700">
              {data.search_text}
            </div>
          ) : data.snippet ? (
            <div className="whitespace-pre-wrap text-sm italic leading-relaxed text-surface-400">
              {data.snippet}
            </div>
          ) : (
            <div className="text-sm italic text-surface-300">No content</div>
          )}
        </div>
      )}
    </div>
  )
}

function HtmlBody({ html }: { html: string }) {
  const sanitized = sanitizeHtml(html)

  return (
    <div
      className="flex-1 overflow-y-auto p-2"
      dangerouslySetInnerHTML={{ __html: sanitized }}
      style={{ overflowWrap: 'break-word' }}
    />
  )
}

function formatParticipants(participants: CommunicationParticipant[]): string {
  const MAX_SHOWN = 3
  const names = participants.map(p => p.name || p.address)
  if (names.length <= MAX_SHOWN) {
    return names.join(', ')
  }
  return `${names.slice(0, MAX_SHOWN).join(', ')} +${names.length - MAX_SHOWN} others`
}

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
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
      <div className="h-5 w-64 animate-pulse rounded bg-surface-200" />
      <div className="h-px bg-surface-200" />
      <div className="space-y-2">
        <div className="h-4 w-full animate-pulse rounded bg-surface-200" />
        <div className="h-4 w-full animate-pulse rounded bg-surface-200" />
        <div className="h-4 w-3/4 animate-pulse rounded bg-surface-200" />
      </div>
    </div>
  )
}
