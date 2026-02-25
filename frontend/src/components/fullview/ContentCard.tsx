import { useState } from 'react'
import { ChevronRight, ChevronDown, Paperclip, Download } from 'lucide-react'
import { format, isToday, isThisYear } from 'date-fns'
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

/** Format timestamp as two lines: date on top, time below */
function formatTimestampTwoLine(isoString: string | null | undefined): { datePart: string; timePart: string } | null {
  if (!isoString) return null
  const date = new Date(isoString)
  if (isNaN(date.getTime())) return null

  const timePart = format(date, 'h:mm a')
  if (isToday(date)) {
    return { datePart: 'Today', timePart }
  }
  if (isThisYear(date)) {
    return { datePart: format(date, 'MMM d'), timePart }
  }
  return { datePart: format(date, 'MMM d, yyyy'), timePart }
}

/**
 * Split email HTML into primary and quoted zones.
 * Detects common quote/forward markers and splits at the first match.
 */
function splitEmailZones(html: string): { primaryHtml: string; quotedHtml: string | null } {
  // Detection patterns for quote/forward boundaries
  const patterns = [
    // "On [date], [name] wrote:" — Gmail/Apple Mail
    /On\s+.{5,80}\s+wrote:\s*/i,
    // Gmail forward marker
    /---------- Forwarded message ----------/,
    // Outlook forward marker
    /-----Original Message-----/,
    // Outlook-style quote header block (From: ... Sent: ... To: ... Subject:)
    /From:\s*.+?(?:\r?\n|\s)Sent:\s*.+?(?:\r?\n|\s)To:\s*.+?(?:\r?\n|\s)Subject:/s,
  ]

  // Also check for <blockquote> tags — split at the first one
  const blockquoteIdx = html.search(/<blockquote[\s>]/i)

  let earliestIdx = -1

  for (const pattern of patterns) {
    const match = html.search(pattern)
    if (match !== -1 && (earliestIdx === -1 || match < earliestIdx)) {
      earliestIdx = match
    }
  }

  // Use blockquote position if it's earlier
  if (blockquoteIdx !== -1 && (earliestIdx === -1 || blockquoteIdx < earliestIdx)) {
    earliestIdx = blockquoteIdx
  }

  if (earliestIdx === -1 || earliestIdx === 0) {
    return { primaryHtml: html, quotedHtml: null }
  }

  return {
    primaryHtml: html.slice(0, earliestIdx),
    quotedHtml: html.slice(earliestIdx),
  }
}

function ContactLink({
  participant,
  className,
  children,
  onClose,
}: {
  participant: CommunicationFullParticipant
  className?: string
  children: React.ReactNode
  onClose: () => void
}) {
  const setActiveEntityType = useNavigationStore((s) => s.setActiveEntityType)
  const setSelectedRow = useNavigationStore((s) => s.setSelectedRow)

  if (participant.contact_id) {
    return (
      <button
        className={`text-primary-600 hover:underline ${className ?? ''}`}
        onClick={(e) => {
          e.stopPropagation()
          setActiveEntityType('contact')
          setSelectedRow(participant.contact_id!, -1)
          onClose()
        }}
      >
        {children}
      </button>
    )
  }

  return <span className={className}>{children}</span>
}

/**
 * Build a capped recipient list with current-user-first and "+X Others" overflow.
 * Returns array of display elements.
 */
function RecipientLine({
  label,
  participants,
  onClose,
}: {
  label: string
  participants: CommunicationFullParticipant[]
  onClose: () => void
}) {
  if (participants.length === 0) return null

  const MAX_NAMES = 3

  // Sort: account owner first, then by last name
  const sorted = [...participants].sort((a, b) => {
    if (a.is_account_owner && !b.is_account_owner) return -1
    if (!a.is_account_owner && b.is_account_owner) return 1
    const aName = a.contact_name || a.name || a.address || ''
    const bName = b.contact_name || b.name || b.address || ''
    const aLast = aName.split(' ').pop() ?? ''
    const bLast = bName.split(' ').pop() ?? ''
    return aLast.localeCompare(bLast, undefined, { sensitivity: 'base' })
  })

  const visible = sorted.slice(0, MAX_NAMES)
  const overflowCount = sorted.length - MAX_NAMES

  return (
    <div className="flex gap-1.5 text-sm">
      <span className="shrink-0 text-surface-400">{label}:</span>
      <span className="text-surface-600">
        {visible.map((p, i) => {
          const displayName = p.contact_name || p.name || p.address
          return (
            <span key={i}>
              {i > 0 && ', '}
              {p.is_account_owner ? (
                <ContactLink participant={p} className="font-bold" onClose={onClose}>
                  {displayName}
                </ContactLink>
              ) : (
                <ContactLink participant={p} onClose={onClose}>
                  {displayName}
                </ContactLink>
              )}
            </span>
          )
        })}
        {overflowCount > 0 && (
          <span className="ml-1 text-surface-400">+{overflowCount} Others</span>
        )}
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

  // Two-zone email body
  const emailZones = isEmailLike && data.cleaned_html
    ? splitEmailZones(sanitizeHtml(data.cleaned_html))
    : null

  const timestamp = formatTimestampTwoLine(data.timestamp)

  return (
    <div className="flex flex-col">
      {/* Header — channel-specific */}
      {isEmailLike ? (
        <div className="border-b border-surface-200 px-5 py-3">
          {/* Sender + Timestamp row */}
          <div className="flex items-start justify-between">
            <div className="min-w-0 flex-1">
              {/* Sender display name — large, bold */}
              {senderParticipants.length > 0 && (
                <>
                  <div className="text-base font-bold text-surface-900">
                    <ContactLink participant={senderParticipants[0]} onClose={onClose}>
                      {senderParticipants[0].contact_name || senderParticipants[0].name || senderParticipants[0].address}
                    </ContactLink>
                  </div>
                  {/* Sender email — smaller, lighter (only if name differs from address) */}
                  {senderParticipants[0].address &&
                    (senderParticipants[0].contact_name || senderParticipants[0].name) && (
                    <div className="text-sm text-surface-400">
                      {senderParticipants[0].address}
                    </div>
                  )}
                </>
              )}
            </div>
            {/* Timestamp — right-aligned, two lines */}
            {timestamp && (
              <div className="shrink-0 text-right text-sm text-surface-500">
                <div>{timestamp.datePart}</div>
                <div>{timestamp.timePart}</div>
              </div>
            )}
          </div>

          {/* Recipients */}
          <div className="mt-2 space-y-0.5">
            <RecipientLine label="To" participants={toParticipants} onClose={onClose} />
            <RecipientLine label="CC" participants={ccParticipants} onClose={onClose} />
            <RecipientLine label="BCC" participants={bccParticipants} onClose={onClose} />
          </div>
        </div>
      ) : (
        <div className="border-b border-surface-200 px-5 py-3">
          <div className="flex items-start justify-between">
            <div className="text-sm font-semibold text-surface-900">
              {isPhoneLike && !isManualEntry
                ? `Call with ${allParticipantNames.join(', ') || 'Unknown'}`
                : isManualEntry
                  ? `${data.channel === 'video_manual' ? 'Video meeting' : data.channel === 'in_person' ? 'Meeting' : data.channel === 'note' ? 'Note' : 'Call'} with ${allParticipantNames.join(', ') || 'Unknown'}`
                  : `${allParticipantNames.join(', ') || data.sender_name || 'Unknown'}`
              }
            </div>
            {timestamp && (
              <div className="shrink-0 text-right text-sm text-surface-500">
                <div>{timestamp.datePart}</div>
                <div>{timestamp.timePart}</div>
              </div>
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

      {/* Subject — largest/boldest text on the card */}
      {data.subject && (
        <div className="border-b border-surface-200 px-5 py-3">
          <h2 className="text-lg font-bold text-surface-900">{data.subject}</h2>
        </div>
      )}

      {/* Body */}
      {emailZones ? (
        <div className="px-5 py-4" style={{ overflowWrap: 'break-word' }}>
          {/* Primary zone — full contrast */}
          <div dangerouslySetInnerHTML={{ __html: emailZones.primaryHtml }} />

          {/* Quoted zone — vertical bar, indent, reduced contrast */}
          {emailZones.quotedHtml && (
            <div
              className="mt-4 border-l-3 border-surface-300 pl-4 text-surface-500 [&_blockquote]:ml-2 [&_blockquote]:border-l-2 [&_blockquote]:border-surface-200 [&_blockquote]:pl-3"
              dangerouslySetInnerHTML={{ __html: emailZones.quotedHtml }}
            />
          )}
        </div>
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
