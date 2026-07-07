import { useRef, useEffect, useState, useMemo, useCallback } from 'react'
import { CHANNEL_ICONS, CHANNEL_LABELS } from '../../lib/channelIcons.ts'
import { formatTimestamp } from '../../lib/formatTimestamp.ts'
import { sanitizeHtml } from '../../lib/sanitizeHtml.ts'
import { useNavigationStore } from '../../stores/navigation.ts'
import { Paperclip, ArrowUpDown } from 'lucide-react'
import type { ConversationCommunication } from '../../types/api.ts'
import type { ParticipantColorMap } from '../../lib/participantColors.ts'

interface ConversationTimelineCardProps {
  communications: ConversationCommunication[]
  colorMap: ParticipantColorMap
  onNavigateAway: () => void
}

/** Build the "→ recipient" suffix with +N overflow */
function recipientSuffix(c: ConversationCommunication): string | null {
  if (!c.recipient_name) return null
  const extra = c.recipient_count - 1
  if (extra > 0) return `${c.recipient_name} +${extra}`
  return c.recipient_name
}

export function ConversationTimelineCard({ communications, colorMap, onNavigateAway }: ConversationTimelineCardProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const entryRefs = useRef<Map<string, HTMLDivElement>>(new Map())
  const setActiveEntityType = useNavigationStore((s) => s.setActiveEntityType)
  const setSelectedRow = useNavigationStore((s) => s.setSelectedRow)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [focusedCommId, setFocusedCommId] = useState<string | null>(null)

  const sorted = useMemo(() => {
    if (sortDir === 'asc') return communications
    return [...communications].reverse()
  }, [communications, sortDir])

  // Auto-scroll to bottom (most recent) on load when ASC
  useEffect(() => {
    const el = scrollRef.current
    if (el && sortDir === 'asc') {
      el.scrollTop = el.scrollHeight
    }
  }, [communications.length, sortDir])

  // Open focused communication in the communication view
  const openCommunication = useCallback((commId: string) => {
    setActiveEntityType('communication')
    setSelectedRow(commId, -1)
    onNavigateAway()
  }, [setActiveEntityType, setSelectedRow, onNavigateAway])

  // Keyboard navigation: arrow keys between entries, Enter to open
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (!focusedCommId || sorted.length === 0) return

    const currentIdx = sorted.findIndex((c) => c.id === focusedCommId)
    if (currentIdx === -1) return

    if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (currentIdx < sorted.length - 1) {
        const nextId = sorted[currentIdx + 1].id
        setFocusedCommId(nextId)
        entryRefs.current.get(nextId)?.scrollIntoView({ block: 'nearest' })
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      if (currentIdx > 0) {
        const prevId = sorted[currentIdx - 1].id
        setFocusedCommId(prevId)
        entryRefs.current.get(prevId)?.scrollIntoView({ block: 'nearest' })
      }
    } else if (e.key === 'Enter') {
      e.preventDefault()
      openCommunication(focusedCommId)
    }
  }, [focusedCommId, sorted, openCommunication])

  if (communications.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center p-8 text-sm text-surface-400">
        No communications in this conversation yet.
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-col" onKeyDown={handleKeyDown} tabIndex={-1}>
      {/* Timeline header with sort toggle */}
      <div className="flex shrink-0 items-center justify-between border-b border-surface-100 px-4 py-1.5">
        <span className="text-xs text-surface-400">
          {communications.length} message{communications.length !== 1 ? 's' : ''}
        </span>
        <button
          onClick={() => setSortDir((d) => d === 'asc' ? 'desc' : 'asc')}
          className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs text-surface-500 hover:bg-surface-100"
        >
          <ArrowUpDown size={12} />
          {sortDir === 'asc' ? 'Oldest First' : 'Newest First'}
        </button>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="divide-y divide-surface-100">
          {sorted.map((c) => (
            <TimelineEntry
              key={c.id}
              comm={c}
              colorMap={colorMap}
              isFocused={focusedCommId === c.id}
              onFocus={() => setFocusedCommId(c.id)}
              onOpen={() => openCommunication(c.id)}
              onNavigateToContact={(contactId) => {
                setActiveEntityType('contact')
                setSelectedRow(contactId, -1)
                onNavigateAway()
              }}
              ref={(el) => {
                if (el) entryRefs.current.set(c.id, el)
                else entryRefs.current.delete(c.id)
              }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

/* --- Timeline Entry --- */

import { forwardRef } from 'react'

interface TimelineEntryProps {
  comm: ConversationCommunication
  colorMap: ParticipantColorMap
  isFocused: boolean
  onFocus: () => void
  onOpen: () => void
  onNavigateToContact: (contactId: string) => void
}

const TimelineEntry = forwardRef<HTMLDivElement, TimelineEntryProps>(
  function TimelineEntry({ comm, colorMap, isFocused, onFocus, onOpen, onNavigateToContact }, ref) {
    const ChannelIcon = CHANNEL_ICONS[comm.channel] ?? CHANNEL_ICONS.email
    const senderLabel = comm.sender_name || comm.sender_address || CHANNEL_LABELS[comm.channel] || comm.channel
    const senderAddr = comm.sender_address || senderLabel
    const circleStyle = colorMap.getCircleStyle(senderAddr)
    const rowTint = colorMap.getRowTint(senderAddr)
    const recipient = recipientSuffix(comm)

    // Render cleaned_html content directly (PRD: always rendered, no truncation)
    const hasHtml = !!comm.cleaned_html
    const contentHtml = hasHtml ? sanitizeHtml(comm.cleaned_html!) : null

    return (
      <div
        ref={ref}
        className={`group px-4 py-3 cursor-pointer ${isFocused ? 'ring-1 ring-inset ring-primary-300' : ''}`}
        style={{ backgroundColor: rowTint }}
        onClick={onFocus}
        onDoubleClick={onOpen}
      >
        <div className="flex items-start gap-3">
          {/* Colored contact circle */}
          <div
            className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-medium"
            style={circleStyle}
          >
            {senderLabel.charAt(0).toUpperCase()}
          </div>

          <div className="min-w-0 flex-1">
            {/* Identity line: channel icon + sender → recipient */}
            <div className="flex items-start gap-2">
              <div className="flex min-w-0 flex-wrap items-center gap-1.5">
                <ChannelIcon size={14} className="shrink-0 text-surface-400" />
                {/* Sender name — clickable link to Contact if resolved */}
                {comm.sender_contact_id ? (
                  <button
                    className="truncate text-sm font-semibold text-primary-600 hover:underline"
                    onClick={(e) => {
                      e.stopPropagation()
                      onNavigateToContact(comm.sender_contact_id!)
                    }}
                  >
                    {senderLabel}
                  </button>
                ) : (
                  <span className="truncate text-sm font-semibold text-surface-800">
                    {senderLabel}
                  </span>
                )}
                {/* → Recipient(s) */}
                {recipient && (
                  <span className="text-sm text-surface-400">
                    → {recipient}
                  </span>
                )}
              </div>
              {/* Timestamp — right-aligned, same-sized font */}
              <span className="ml-auto shrink-0 text-sm text-surface-400">
                {formatTimestamp(comm.timestamp)}
              </span>
            </div>

            {/* Communication content — cleaned_html rendered as formatted HTML */}
            <div className="mt-2 text-sm leading-relaxed text-surface-600">
              {contentHtml ? (
                <div
                  className="prose prose-sm max-w-none [&_*]:!text-sm [&_*]:!leading-relaxed [&_img]:max-w-full [&_img]:h-auto [&_table]:w-full [&_table]:text-sm"
                  dangerouslySetInnerHTML={{ __html: contentHtml }}
                />
              ) : (
                comm.snippet || <span className="italic text-surface-300">No content</span>
              )}
            </div>

            {/* Attachment indicator + metadata badges */}
            {(comm.attachment_count > 0 || !comm.is_primary) && (
              <div className="mt-2 flex items-center gap-2">
                {comm.attachment_count > 0 && (
                  <span className="flex items-center gap-1 text-xs text-surface-400">
                    <Paperclip size={11} />
                    {comm.attachment_count} {comm.attachment_count === 1 ? 'attachment' : 'attachments'}
                  </span>
                )}
                {!comm.is_primary && (
                  <span className="rounded bg-amber-50 px-1.5 py-0.5 text-xs text-amber-600">
                    secondary
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }
)
