import { useState } from 'react'
import { ChevronRight, ChevronDown, Paperclip, Download } from 'lucide-react'
import { sanitizeHtml } from '../../lib/sanitizeHtml.ts'
import { useNavigationStore } from '../../stores/navigation.ts'
import type { CommunicationFullData, CommunicationFullParticipant } from '../../types/api.ts'

interface ContentCardProps {
  data: CommunicationFullData
  onClose: () => void
}

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m} min`
  return `${seconds}s`
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function ParticipantName({
  participant,
  showEmail,
  onClose,
}: {
  participant: CommunicationFullParticipant
  showEmail?: boolean
  onClose: () => void
}) {
  const setActiveEntityType = useNavigationStore((s) => s.setActiveEntityType)
  const setSelectedRow = useNavigationStore((s) => s.setSelectedRow)
  const displayName = participant.contact_name || participant.name || participant.address

  if (participant.contact_id) {
    return (
      <button
        className="text-primary-600 hover:underline"
        onClick={(e) => {
          e.stopPropagation()
          setActiveEntityType('contact')
          setSelectedRow(participant.contact_id!, -1)
          onClose()
        }}
      >
        {displayName}
        {showEmail && participant.address && (
          <span className="ml-1 text-surface-400">&lt;{participant.address}&gt;</span>
        )}
      </button>
    )
  }

  return (
    <span>
      {displayName}
      {showEmail && participant.address && displayName !== participant.address && (
        <span className="ml-1 text-surface-400">&lt;{participant.address}&gt;</span>
      )}
    </span>
  )
}

function ParticipantList({
  label,
  participants,
  onClose,
}: {
  label: string
  participants: CommunicationFullParticipant[]
  onClose: () => void
}) {
  if (participants.length === 0) return null
  return (
    <div className="flex gap-1.5">
      <span className="shrink-0 font-medium text-surface-400">{label}:</span>
      <span className="text-surface-600">
        {participants.map((p, i) => (
          <span key={i}>
            {i > 0 && ', '}
            <ParticipantName participant={p} showEmail onClose={onClose} />
          </span>
        ))}
      </span>
    </div>
  )
}

export function ContentCard({ data, onClose }: ContentCardProps) {
  const [showOriginal, setShowOriginal] = useState(false)

  const isEmailLike = data.channel === 'email'
  const isPhoneLike = data.channel === 'phone' || data.channel === 'phone_manual' ||
                      data.channel === 'video' || data.channel === 'video_manual'
  const isManualEntry = data.channel === 'phone_manual' || data.channel === 'video_manual' ||
                        data.channel === 'in_person' || data.channel === 'note'

  const senderParticipants = data.participants.filter((p) => p.role === 'from')
  const toParticipants = data.participants.filter((p) => p.role === 'to')
  const ccParticipants = data.participants.filter((p) => p.role === 'cc')
  const bccParticipants = data.participants.filter((p) => p.role === 'bcc')

  // For non-email channels, all participants in one line
  const allParticipantNames = data.participants
    .filter((p) => !p.is_account_owner)
    .map((p) => p.contact_name || p.name || p.address)
    .filter(Boolean)

  return (
    <div className="flex flex-col">
      {/* Header — channel-specific */}
      {isEmailLike ? (
        <div className="space-y-1 border-b border-surface-200 px-5 py-3 text-sm">
          {/* Sender */}
          {senderParticipants.length > 0 && (
            <div className="font-semibold text-surface-900">
              <ParticipantName participant={senderParticipants[0]} showEmail onClose={onClose} />
            </div>
          )}
          {/* Recipients */}
          <ParticipantList label="To" participants={toParticipants} onClose={onClose} />
          <ParticipantList label="CC" participants={ccParticipants} onClose={onClose} />
          <ParticipantList label="BCC" participants={bccParticipants} onClose={onClose} />
        </div>
      ) : (
        <div className="border-b border-surface-200 px-5 py-3">
          <div className="text-sm font-semibold text-surface-900">
            {isPhoneLike && !isManualEntry
              ? `Call with ${allParticipantNames.join(', ') || 'Unknown'}`
              : isManualEntry
                ? `${data.channel === 'video_manual' ? 'Video meeting' : data.channel === 'in_person' ? 'Meeting' : data.channel === 'note' ? 'Note' : 'Call'} with ${allParticipantNames.join(', ') || 'Unknown'}`
                : `${allParticipantNames.join(', ') || data.sender_name || 'Unknown'}`
            }
            {data.direction && (
              <span className="ml-2 text-xs font-normal text-surface-400">
                {data.direction === 'inbound' ? '← Inbound' : data.direction === 'outbound' ? '→ Outbound' : '↔ Meeting'}
              </span>
            )}
          </div>
          {data.duration_seconds != null && (
            <div className="mt-0.5 text-xs text-surface-500">
              Duration: {formatDuration(data.duration_seconds)}
            </div>
          )}
          {data.phone_number_from && (
            <div className="mt-0.5 text-xs text-surface-400">
              {data.phone_number_from}
            </div>
          )}
        </div>
      )}

      {/* Subject */}
      {data.subject && (
        <div className="border-b border-surface-200 px-5 py-3">
          <h2 className="text-base font-semibold text-surface-900">{data.subject}</h2>
        </div>
      )}

      {/* Body */}
      {isEmailLike && data.cleaned_html ? (
        <div
          className="px-5 py-4"
          dangerouslySetInnerHTML={{ __html: sanitizeHtml(data.cleaned_html) }}
          style={{ overflowWrap: 'break-word' }}
        />
      ) : (
        <div className="px-5 py-4">
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

      {/* Attachments */}
      {data.attachments.length > 0 && (
        <div className="border-t border-surface-200 px-5 py-3">
          <div className="mb-2 flex items-center gap-2 text-xs font-medium text-surface-500">
            <Paperclip size={12} />
            Attachments ({data.attachments.length})
          </div>
          <div className="space-y-1.5">
            {data.attachments.map((att) => (
              <div key={att.id} className="flex items-center justify-between rounded bg-surface-50 px-3 py-2 text-sm">
                <span className="truncate text-surface-700">{att.filename}</span>
                <div className="flex shrink-0 items-center gap-3 text-xs text-surface-400">
                  {att.size_bytes != null && <span>{formatFileSize(att.size_bytes)}</span>}
                  <button
                    className="text-surface-400 hover:text-surface-600 disabled:opacity-40"
                    disabled
                    title="Download (coming soon)"
                  >
                    <Download size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* View Original expander */}
      {isEmailLike && data.original_text && (
        <div className="border-t border-surface-200">
          <button
            onClick={() => setShowOriginal(!showOriginal)}
            className="flex w-full items-center gap-1.5 px-5 py-2.5 text-xs font-medium text-surface-500 hover:bg-surface-50"
          >
            {showOriginal ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            View Original
          </button>
          {showOriginal && (
            <div className="border-t border-surface-100 bg-surface-50 px-5 py-3">
              <pre className="whitespace-pre-wrap text-xs leading-relaxed text-surface-600">
                {data.original_text}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
