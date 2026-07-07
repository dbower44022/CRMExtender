import { FolderOpen, MessageSquare, Plus } from 'lucide-react'
import { formatTimestamp } from '../../lib/formatTimestamp.ts'
import { useNavigationStore } from '../../stores/navigation.ts'
import type { ConversationChildPreview } from '../../types/api.ts'

interface ConversationChildrenCardProps {
  children: ConversationChildPreview[]
  onNavigateAway: () => void
}

export function ConversationChildrenCard({ children, onNavigateAway }: ConversationChildrenCardProps) {
  const setActiveEntityType = useNavigationStore((s) => s.setActiveEntityType)
  const setSelectedRow = useNavigationStore((s) => s.setSelectedRow)

  // Suppressed for non-aggregate conversations (caller checks is_aggregate)
  if (children.length === 0) return null

  const navigateTo = (convId: string) => {
    setActiveEntityType('conversation')
    setSelectedRow(convId, -1)
    onNavigateAway()
  }

  // Sort by last_activity_at DESC (most recent first)
  const sorted = [...children].sort((a, b) => {
    const aTime = a.last_activity_at ?? ''
    const bTime = b.last_activity_at ?? ''
    return bTime.localeCompare(aTime)
  })

  return (
    <div className="rounded-lg border border-surface-200 bg-white">
      <div className="flex items-center justify-between border-b border-surface-200 px-4 py-2.5">
        <span className="text-xs font-semibold uppercase text-surface-500">
          Child Conversations ({children.length})
        </span>
        <button
          disabled
          className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs text-surface-300"
          title="Add child conversation (coming soon)"
        >
          <Plus size={12} />
          Add
        </button>
      </div>

      <div className="divide-y divide-surface-100">
        {sorted.map((child) => {
          const TypeIcon = child.is_aggregate ? FolderOpen : MessageSquare
          return (
            <div key={child.id} className="px-4 py-2.5">
              <div className="flex items-center gap-2">
                <TypeIcon size={14} className="shrink-0 text-surface-400" />
                <button
                  className="min-w-0 truncate text-sm text-primary-600 hover:underline"
                  onClick={() => navigateTo(child.id)}
                >
                  {child.title || 'Untitled Conversation'}
                </button>
                {child.status && (
                  <span className="shrink-0 rounded bg-surface-100 px-1.5 py-0.5 text-xs capitalize text-surface-500">
                    {child.status}
                  </span>
                )}
              </div>
              <div className="mt-0.5 flex items-center gap-2 text-xs text-surface-400">
                <span>{child.communication_count} message{child.communication_count !== 1 ? 's' : ''}</span>
                {child.child_count > 0 && (
                  <span>· {child.child_count} sub-conversation{child.child_count !== 1 ? 's' : ''}</span>
                )}
                {child.last_activity_at && (
                  <span className="ml-auto">{formatTimestamp(child.last_activity_at)}</span>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
