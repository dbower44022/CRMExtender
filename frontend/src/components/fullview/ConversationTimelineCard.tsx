import { useRef, useEffect } from 'react'
import { CHANNEL_ICONS, CHANNEL_LABELS } from '../../lib/channelIcons.ts'
import { formatTimestamp } from '../../lib/formatTimestamp.ts'
import { useNavigationStore } from '../../stores/navigation.ts'
import { ArrowDownRight, ArrowUpRight, ExternalLink } from 'lucide-react'
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
        No communications in this conversation.
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
          const isOutbound = c.direction === 'outbound'
          const DirectionIcon = isOutbound ? ArrowUpRight : ArrowDownRight
          const dirColor = isOutbound ? 'text-blue-400' : 'text-green-400'

          return (
            <div key={c.id} className="group px-4 py-3 hover:bg-surface-25">
              <div className="flex items-start gap-3">
                {/* Avatar */}
                <div
                  className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-medium text-white"
                  style={{ backgroundColor: `hsl(${hue}, 55%, 50%)` }}
                >
                  {senderLabel.charAt(0).toUpperCase()}
                </div>

                <div className="min-w-0 flex-1">
                  {/* Top row: sender + timestamp + channel + direction */}
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-medium text-surface-800">
                      {senderLabel}
                    </span>
                    {c.sender_name && c.sender_address && (
                      <span className="hidden truncate text-xs text-surface-400 sm:inline">
                        &lt;{c.sender_address}&gt;
                      </span>
                    )}
                    <span className="ml-auto flex shrink-0 items-center gap-1.5 text-xs text-surface-400">
                      <ChannelIcon size={12} />
                      <DirectionIcon size={12} className={dirColor} />
                      {formatTimestamp(c.timestamp)}
                    </span>
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

                  {/* Metadata badges */}
                  <div className="mt-1.5 flex items-center gap-2">
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
                    {/* View full link */}
                    <button
                      onClick={() => {
                        setActiveEntityType('communication')
                        setSelectedRow(c.id, -1)
                        onNavigateAway()
                      }}
                      className="ml-auto hidden items-center gap-1 rounded px-1.5 py-0.5 text-xs text-surface-400 hover:bg-surface-100 hover:text-surface-600 group-hover:flex"
                    >
                      <ExternalLink size={10} />
                      View full
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
