import { Calendar } from 'lucide-react'
import { formatTimestamp } from '../../lib/formatTimestamp.ts'
import { useNavigationStore } from '../../stores/navigation.ts'
import type { ConversationEvent } from '../../types/api.ts'

interface ConversationEventsCardProps {
  events: ConversationEvent[]
  onNavigateAway: () => void
}

export function ConversationEventsCard({ events, onNavigateAway }: ConversationEventsCardProps) {
  const setActiveEntityType = useNavigationStore((s) => s.setActiveEntityType)
  const setSelectedRow = useNavigationStore((s) => s.setSelectedRow)

  if (events.length === 0) return null

  return (
    <div className="rounded-lg border border-surface-200 bg-white">
      <div className="flex items-center gap-2 border-b border-surface-200 px-4 py-2.5">
        <Calendar size={14} className="text-surface-400" />
        <span className="text-xs font-semibold uppercase text-surface-500">
          Events ({events.length})
        </span>
      </div>
      <div className="divide-y divide-surface-100">
        {events.map((e) => (
          <div key={e.id} className="px-4 py-2.5">
            <div className="flex items-center justify-between gap-2">
              <button
                className="truncate text-sm font-medium text-primary-600 hover:underline"
                onClick={() => {
                  setActiveEntityType('event')
                  setSelectedRow(e.id, -1)
                  onNavigateAway()
                }}
              >
                {e.title || 'Untitled Event'}
              </button>
              {e.event_type && (
                <span className="shrink-0 rounded bg-surface-100 px-1.5 py-0.5 text-xs text-surface-500">
                  {e.event_type}
                </span>
              )}
            </div>
            <div className="mt-0.5 flex items-center gap-2 text-xs text-surface-400">
              {e.start_datetime && <span>{formatTimestamp(e.start_datetime)}</span>}
              {e.status && <span className="capitalize">{e.status}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
