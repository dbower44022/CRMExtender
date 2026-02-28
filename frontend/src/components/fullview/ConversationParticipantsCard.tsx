import { useState, useMemo } from 'react'
import { useNavigationStore } from '../../stores/navigation.ts'
import type { ConversationFullParticipant } from '../../types/api.ts'
import type { ParticipantColorMap } from '../../lib/participantColors.ts'

interface ConversationParticipantsCardProps {
  participants: ConversationFullParticipant[]
  colorMap: ParticipantColorMap
  accountOwnerEmail: string | null
  onNavigateAway: () => void
}

const VISIBLE_LIMIT = 6

export function ConversationParticipantsCard({
  participants,
  colorMap,
  accountOwnerEmail,
  onNavigateAway,
}: ConversationParticipantsCardProps) {
  const setActiveEntityType = useNavigationStore((s) => s.setActiveEntityType)
  const setSelectedRow = useNavigationStore((s) => s.setSelectedRow)
  const [expanded, setExpanded] = useState(false)

  // Sort: account owner first, then by communication_count DESC
  const sorted = useMemo(() => {
    if (!accountOwnerEmail) return participants
    return [...participants].sort((a, b) => {
      const aOwner = a.address.toLowerCase() === accountOwnerEmail.toLowerCase()
      const bOwner = b.address.toLowerCase() === accountOwnerEmail.toLowerCase()
      if (aOwner && !bOwner) return -1
      if (!aOwner && bOwner) return 1
      return 0
    })
  }, [participants, accountOwnerEmail])

  if (participants.length === 0) return null

  const visible = expanded ? sorted : sorted.slice(0, VISIBLE_LIMIT)
  const hiddenCount = sorted.length - VISIBLE_LIMIT

  return (
    <div className="rounded-lg border border-surface-200 bg-white">
      <div className="border-b border-surface-200 px-4 py-2.5 text-xs font-semibold uppercase text-surface-500">
        Participants ({participants.length})
      </div>
      <div className="divide-y divide-surface-100">
        {visible.map((p, i) => {
          const isOwner = colorMap.isAccountOwner(p.address)
          const circleStyle = colorMap.getCircleStyle(p.address)
          const displayName = p.contact_name || p.name || p.address
          return (
            <div key={i} className="px-4 py-2.5">
              <div className="flex items-center gap-2.5">
                {/* Color swatch */}
                <div
                  className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[10px] font-medium"
                  style={circleStyle}
                >
                  {displayName.charAt(0).toUpperCase()}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    {p.contact_id ? (
                      <button
                        className="truncate text-sm font-medium text-primary-600 hover:underline"
                        onClick={() => {
                          setActiveEntityType('contact')
                          setSelectedRow(p.contact_id!, -1)
                          onNavigateAway()
                        }}
                      >
                        {displayName}
                      </button>
                    ) : (
                      <span className="truncate text-sm text-surface-700">
                        {displayName}
                      </span>
                    )}
                    {isOwner && (
                      <span className="shrink-0 rounded bg-primary-50 px-1.5 py-0.5 text-[10px] font-medium text-primary-600">
                        You
                      </span>
                    )}
                  </div>
                  {p.address && (
                    <div className="truncate text-xs text-surface-400">
                      {p.address}
                    </div>
                  )}
                </div>
                <div className="shrink-0 ml-2 text-right">
                  <div className="text-xs text-surface-500">
                    {p.communication_count} msg{p.communication_count !== 1 ? 's' : ''}
                  </div>
                </div>
              </div>
              {(p.title || p.company_name) && (
                <div className="mt-0.5 truncate pl-8.5 text-xs text-surface-400">
                  {[p.title, p.company_name].filter(Boolean).join(' · ')}
                </div>
              )}
            </div>
          )
        })}
      </div>
      {hiddenCount > 0 && !expanded && (
        <button
          onClick={() => setExpanded(true)}
          className="w-full border-t border-surface-100 px-4 py-2 text-xs text-primary-500 hover:bg-surface-50"
        >
          +{hiddenCount} Other{hiddenCount !== 1 ? 's' : ''}
        </button>
      )}
      {expanded && hiddenCount > 0 && (
        <button
          onClick={() => setExpanded(false)}
          className="w-full border-t border-surface-100 px-4 py-2 text-xs text-primary-500 hover:bg-surface-50"
        >
          Show Less
        </button>
      )}
    </div>
  )
}
