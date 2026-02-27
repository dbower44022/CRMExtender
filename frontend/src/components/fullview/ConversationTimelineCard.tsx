import { useRef, useEffect } from 'react'
import { CHANNEL_ICONS, CHANNEL_LABELS } from '../../lib/channelIcons.ts'
import { formatTimestamp } from '../../lib/formatTimestamp.ts'
import { useNavigationStore } from '../../stores/navigation.ts'
import { ExternalLink, Paperclip } from 'lucide-react'
import type { ConversationCommunication } from '../../types/api.ts'

interface ConversationTimelineCardProps {
  communications: ConversationCommunication[]
  onNavigateAway: () => void
}

/** Hash a string to a hue for avatar background */
function nameHue(s: string): number {
  let hash = 0
  for (let i = 0; i < s.length; i++) {
    hash = s.charCodeAt(i) + ((hash << 5) - hash)
  }
  return Math.abs(hash) % 360
}

/** Build the "→ recipient" suffix per PRD 7.2 */
function recipientSuffix(c: ConversationCommunication): string | null {
  if (!c.recipient_name) return null
  const extra = c.recipient_count - 1
  if (extra > 0) return `${c.recipient_name} +${extra}`
  return c.recipient_name
}

export function ConversationTimelineCard({ communications, onNavigateAway }: ConversationTimelineCardProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const setActiveEntityType = useNavigationStore((s) => s.setActiveEntityType)
  const setSelectedRow = useNavigationStore((s) => s.setSelectedRow)

  // Auto-scroll to bottom (most recent) on load
  useEffect(() => {
    const el = scrollRef.current
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  }, [communications.length])

  if (communications.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center p-8 text-sm text-surface-400">
        No communications in this conversation yet.
      </div>
    )
  }

  return (
    <div ref={scrollRef} className="flex-1 overflow-y-auto">
      <div className="space-y-0 divide-y divide-surface-100">
        {communications.map((c) => {
          const ChannelIcon = CHANNEL_ICONS[c.channel] ?? CHANNEL_ICONS.email
          const senderLabel = c.sender_name || c.sender_address || CHANNEL_LABELS[c.channel] || c.channel
          const hue = nameHue(senderLabel)
          const recipient = recipientSuffix(c)

          return (
            <div
              key={c.id}
              className="group px-4 py-3"
              style={{ backgroundColor: `hsl(${hue}, 30%, 97%)` }}
            >
              <div className="flex items-start gap-3">
                {/* Colored circle */}
                <div
                  className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-medium text-white"
                  style={{ backgroundColor: `hsl(${hue}, 55%, 50%)` }}
                >
                  {senderLabel.charAt(0).toUpperCase()}
                </div>

                <div className="min-w-0 flex-1">
                  {/* Identity line: channel icon + sender → recipient + timestamp */}
                  <div className="flex items-start gap-2">
                    <div className="flex min-w-0 flex-wrap items-center gap-1.5">
                      <ChannelIcon size={14} className="shrink-0 text-surface-400" />
                      {/* Sender — clickable link if resolved */}
                      {c.sender_contact_id ? (
                        <button
                          className="truncate text-sm font-medium text-primary-600 hover:underline"
                          onClick={() => {
                            setActiveEntityType('contact')
                            setSelectedRow(c.sender_contact_id!, -1)
                            onNavigateAway()
                          }}
                        >
                          {senderLabel}
                        </button>
                      ) : (
                        <span className="truncate text-sm font-medium text-surface-800">
                          {senderLabel}
                        </span>
                      )}
                      {/* → Recipient */}
                      {recipient && (
                        <span className="text-sm text-surface-400">
                          → {recipient}
                        </span>
                      )}
                    </div>
                    {/* Timestamp + View Original — right-aligned */}
                    <div className="ml-auto shrink-0 text-right">
                      <div className="text-sm text-surface-400">
                        {formatTimestamp(c.timestamp)}
                      </div>
                      <button
                        onClick={() => {
                          setActiveEntityType('communication')
                          setSelectedRow(c.id, -1)
                          onNavigateAway()
                        }}
                        className="mt-0.5 inline-flex items-center gap-1 text-xs text-primary-500 hover:text-primary-700 hover:underline"
                      >
                        <ExternalLink size={10} />
                        View Original
                      </button>
                    </div>
                  </div>

                  {/* Subject */}
                  {c.subject && (
                    <div className="mt-0.5 truncate text-sm font-medium text-surface-700">
                      {c.subject}
                    </div>
                  )}

                  {/* Snippet or AI summary */}
                  <div className="mt-1 text-sm leading-relaxed text-surface-500">
                    {c.ai_summary || c.snippet || (
                      <span className="italic text-surface-300">No preview</span>
                    )}
                  </div>

                  {/* Attachment indicator + metadata badges */}
                  {(c.attachment_count > 0 || !c.is_primary || (c.assignment_source && c.assignment_source !== 'sync')) && (
                    <div className="mt-1.5 flex items-center gap-2">
                      {c.attachment_count > 0 && (
                        <span className="flex items-center gap-1 text-xs text-surface-400">
                          <Paperclip size={11} />
                          {c.attachment_count} {c.attachment_count === 1 ? 'attachment' : 'attachments'}
                        </span>
                      )}
                      {!c.is_primary && (
                        <span className="rounded bg-amber-50 px-1.5 py-0.5 text-xs text-amber-600">
                          secondary
                        </span>
                      )}
                      {c.assignment_source && c.assignment_source !== 'sync' && (
                        <span className="rounded bg-surface-100 px-1.5 py-0.5 text-xs text-surface-500">
                          {c.assignment_source}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
