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

// ---------- Helpers ----------

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

function formatTimestampTwoLine(isoString: string | null | undefined): { datePart: string; timePart: string } | null {
  if (!isoString) return null
  const date = new Date(isoString)
  if (isNaN(date.getTime())) return null
  const timePart = format(date, 'h:mm a')
  if (isToday(date)) return { datePart: 'Today', timePart }
  if (isThisYear(date)) return { datePart: format(date, 'MMM d'), timePart }
  return { datePart: format(date, 'MMM d, yyyy'), timePart }
}

// ---------- Avatar ----------

const AVATAR_COLORS = [
  '#4f46e5', '#0891b2', '#059669', '#d97706', '#dc2626',
  '#7c3aed', '#2563eb', '#c026d3', '#ea580c', '#0d9488',
]

function getAvatarColor(name: string): string {
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length]
}

function SenderAvatar({ name }: { name: string }) {
  const initial = (name[0] ?? '?').toUpperCase()
  const bg = getAvatarColor(name)
  return (
    <div
      className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-semibold text-white"
      style={{ backgroundColor: bg }}
    >
      {initial}
    </div>
  )
}

// ---------- Two-zone split ----------

function splitEmailZones(html: string): { primaryHtml: string; quotedHtml: string | null } {
  // Text-based patterns (match inline text within the HTML)
  const textPatterns = [
    /On\s+.{5,80}\s+wrote:\s*/i,
    /-{5,}\s*Forwarded message\s*-{5,}/,
    /-{3,}\s*Original Message\s*-{3,}/,
  ]

  // HTML-structural patterns (match container elements used by email clients)
  const htmlPatterns = [
    /<div[^>]+\bid\s*=\s*["']?divRplyFwdMsg["']?[^>]*>/i,          // Outlook forward container
    /<div[^>]+\bid\s*=\s*["']?appendonsend["']?[^>]*>/i,           // Outlook Mobile cutoff
    /<div[^>]+class\s*=\s*["'][^"']*gmail_quote[^"']*["'][^>]*>/i, // Gmail quoted/forward
    /<div[^>]*border-top\s*:\s*solid[^>]*>/i,                      // Outlook styled separator
  ]

  let earliestIdx = -1

  for (const pattern of textPatterns) {
    const match = html.search(pattern)
    if (match !== -1 && (earliestIdx === -1 || match < earliestIdx)) {
      earliestIdx = match
    }
  }

  for (const pattern of htmlPatterns) {
    const match = html.search(pattern)
    if (match !== -1 && (earliestIdx === -1 || match < earliestIdx)) {
      earliestIdx = match
    }
  }

  const blockquoteIdx = html.search(/<blockquote[\s>]/i)
  if (blockquoteIdx !== -1 && (earliestIdx === -1 || blockquoteIdx < earliestIdx)) {
    earliestIdx = blockquoteIdx
  }

  if (earliestIdx === -1 || earliestIdx === 0) {
    return { primaryHtml: html, quotedHtml: null }
  }

  // Try to back up to a parent <div> wrapper (common in Outlook forwarding structure)
  const before = html.slice(Math.max(0, earliestIdx - 10), earliestIdx)
  const parentDiv = before.match(/<div>\s*$/)
  if (parentDiv) {
    earliestIdx -= parentDiv[0].length
  }

  const primaryHtml = html.slice(0, earliestIdx)

  // If primary zone has no meaningful text (e.g. a forward with no personal note),
  // treat the entire body as primary so the user sees content immediately
  const primaryText = primaryHtml
    .replace(/<style\b[^]*?<\/style\s*>/gi, '')
    .replace(/<title\b[^]*?<\/title\s*>/gi, '')
    .replace(/<[^>]*>/g, '')
    .replace(/&\w+;/g, ' ')
    .replace(/&#\d+;/g, ' ')
    .trim()
  if (primaryText.length === 0) {
    return { primaryHtml: html, quotedHtml: null }
  }

  return {
    primaryHtml,
    quotedHtml: html.slice(earliestIdx),
  }
}

// ---------- Sub-components ----------

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
    <div className="flex gap-1.5 text-[13px] leading-snug">
      <span className="shrink-0 font-medium text-surface-500">{label}:</span>
      <span className="text-surface-700">
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

// ---------- Sender resolution ----------

function resolveSender(data: CommunicationFullData): {
  displayName: string
  emailAddress: string | null
  participant: CommunicationFullParticipant | null
} {
  const fromParticipant = data.participants.find((p) => p.role === 'from') ?? null

  if (fromParticipant) {
    const displayName = fromParticipant.contact_name || fromParticipant.name || fromParticipant.address
    const hasName = !!(fromParticipant.contact_name || fromParticipant.name)
    return {
      displayName,
      emailAddress: hasName ? fromParticipant.address : null,
      participant: fromParticipant,
    }
  }

  const displayName = data.sender_name || data.sender_address || 'Unknown'
  const hasName = !!data.sender_name
  return {
    displayName,
    emailAddress: hasName ? data.sender_address : null,
    participant: null,
  }
}

// ---------- Main component ----------

export function ContentCard({ data, onClose }: ContentCardProps) {
  const [showOriginal, setShowOriginal] = useState(false)
  const [showQuoted, setShowQuoted] = useState(false)

  const isEmailLike = data.channel === 'email'
  const isPhoneLike = data.channel === 'phone' || data.channel === 'phone_manual' ||
                      data.channel === 'video' || data.channel === 'video_manual'
  const isManualEntry = data.channel === 'phone_manual' || data.channel === 'video_manual' ||
                        data.channel === 'in_person' || data.channel === 'note'

  const toParticipants = data.participants.filter((p) => p.role === 'to')
  const ccParticipants = data.participants.filter((p) => p.role === 'cc')
  const bccParticipants = data.participants.filter((p) => p.role === 'bcc')

  const allParticipantNames = data.participants
    .filter((p) => !p.is_account_owner)
    .map((p) => p.contact_name || p.name || p.address)
    .filter(Boolean)

  const emailZones = isEmailLike && data.cleaned_html
    ? splitEmailZones(sanitizeHtml(data.cleaned_html))
    : null

  const timestamp = formatTimestampTwoLine(data.timestamp)
  const sender = isEmailLike ? resolveSender(data) : null

  return (
    <div className="flex flex-col">
      {/* ── Email header ── */}
      {isEmailLike ? (
        <div className="border-b border-surface-200 px-6 py-4">
          {/* Sender row: avatar + name/email + timestamp */}
          <div className="flex items-start gap-3">
            <SenderAvatar name={sender!.displayName} />
            <div className="min-w-0 flex-1">
              <div className="flex items-start justify-between">
                <div className="min-w-0">
                  <div className="text-lg font-bold leading-tight text-surface-900">
                    {sender!.participant ? (
                      <ContactLink participant={sender!.participant} onClose={onClose}>
                        {sender!.displayName}
                      </ContactLink>
                    ) : (
                      <span>{sender!.displayName}</span>
                    )}
                  </div>
                  {sender!.emailAddress && (
                    <div className="mt-0.5 text-[13px] text-surface-500">
                      {sender!.emailAddress}
                    </div>
                  )}
                </div>
                {timestamp && (
                  <div className="shrink-0 pl-4 text-right text-[13px] leading-tight text-surface-400">
                    <div>{timestamp.datePart}</div>
                    <div className="mt-0.5">{timestamp.timePart}</div>
                  </div>
                )}
              </div>

              {/* Recipients — below sender name, inside the avatar-indented area */}
              <div className="mt-2.5 space-y-0.5">
                <RecipientLine label="To" participants={toParticipants} onClose={onClose} />
                <RecipientLine label="CC" participants={ccParticipants} onClose={onClose} />
                <RecipientLine label="BCC" participants={bccParticipants} onClose={onClose} />
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* ── Non-email header ── */
        <div className="border-b border-surface-200 px-6 py-4">
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
              <div className="shrink-0 pl-4 text-right text-[13px] leading-tight text-surface-400">
                <div>{timestamp.datePart}</div>
                <div className="mt-0.5">{timestamp.timePart}</div>
              </div>
            )}
          </div>
          {data.duration_seconds != null && (
            <div className="mt-1 text-xs text-surface-500">
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

      {/* ── Subject ── */}
      {data.subject && (
        <div className="border-b border-surface-200 px-6 py-4">
          <h2 className="text-xl font-bold leading-snug text-surface-900">{data.subject}</h2>
        </div>
      )}

      {/* ── Body ── */}
      {emailZones ? (
        <div className="px-6 py-5">
          {/* Primary zone — new message content, full contrast, controlled typography */}
          <div
            className="email-body"
            dangerouslySetInnerHTML={{ __html: emailZones.primaryHtml }}
          />

          {/* Quoted zone — collapsed by default */}
          {emailZones.quotedHtml && (
            showQuoted ? (
              <>
                <button
                  onClick={() => setShowQuoted(false)}
                  className="mt-4 flex items-center gap-1.5 text-xs font-medium text-surface-400 hover:text-surface-600"
                >
                  <ChevronDown size={12} />
                  Hide quoted text
                </button>
                <div
                  className="email-body-quoted mt-2 border-l-4 border-surface-200 bg-surface-50 py-3 pl-4 pr-3 text-[13px] text-surface-400 [&_blockquote]:my-2 [&_blockquote]:border-l-2 [&_blockquote]:border-surface-200 [&_blockquote]:pl-3"
                  dangerouslySetInnerHTML={{ __html: emailZones.quotedHtml }}
                />
              </>
            ) : (
              <button
                onClick={() => setShowQuoted(true)}
                className="mt-4 flex items-center gap-1.5 text-xs font-medium text-surface-400 hover:text-surface-600"
              >
                <ChevronRight size={12} />
                Show quoted text
              </button>
            )
          )}
        </div>
      ) : (
        <div className="px-6 py-5">
          {data.search_text ? (
            <div className="email-body whitespace-pre-wrap">
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

      {/* ── Attachments ── */}
      {data.attachments.length > 0 && (
        <div className="border-t border-surface-200 px-6 py-3">
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

      {/* ── View Original ── */}
      {isEmailLike && data.original_text && (
        <div className="border-t border-surface-200">
          <button
            onClick={() => setShowOriginal(!showOriginal)}
            className="flex w-full items-center gap-1.5 px-6 py-2.5 text-xs font-medium text-surface-500 hover:bg-surface-50"
          >
            {showOriginal ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            View Original
          </button>
          {showOriginal && (
            <div className="border-t border-surface-100 bg-surface-50 px-6 py-3">
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
