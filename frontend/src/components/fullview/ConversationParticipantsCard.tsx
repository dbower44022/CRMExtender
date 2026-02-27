import { useNavigationStore } from '../../stores/navigation.ts'
import type { ConversationFullParticipant } from '../../types/api.ts'

interface ConversationParticipantsCardProps {
  participants: ConversationFullParticipant[]
  onNavigateAway: () => void
}

export function ConversationParticipantsCard({ participants, onNavigateAway }: ConversationParticipantsCardProps) {
  const setActiveEntityType = useNavigationStore((s) => s.setActiveEntityType)
  const setSelectedRow = useNavigationStore((s) => s.setSelectedRow)

  if (participants.length === 0) return null

  return (
    <div className="rounded-lg border border-surface-200 bg-white">
      <div className="border-b border-surface-200 px-4 py-2.5 text-xs font-semibold uppercase text-surface-500">
        Participants ({participants.length})
      </div>
      <div className="divide-y divide-surface-100">
        {participants.map((p, i) => (
          <div key={i} className="px-4 py-2.5">
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                {p.contact_id ? (
                  <button
                    className="truncate text-sm font-medium text-primary-600 hover:underline"
                    onClick={() => {
                      setActiveEntityType('contact')
                      setSelectedRow(p.contact_id!, -1)
                      onNavigateAway()
                    }}
                  >
                    {p.contact_name || p.name || p.address}
                  </button>
                ) : (
                  <span className="truncate text-sm text-surface-700">
                    {p.name || p.address}
                  </span>
                )}
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
              <div className="mt-0.5 truncate text-xs text-surface-400">
                {[p.title, p.company_name].filter(Boolean).join(' · ')}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
