import { FolderOpen, ExternalLink } from 'lucide-react'
import { useNavigationStore } from '../../stores/navigation.ts'
import type { CommunicationConversation } from '../../types/api.ts'

interface ConversationCardProps {
  conversation: CommunicationConversation | null
  onClose: () => void
}

export function ConversationCard({ conversation, onClose }: ConversationCardProps) {
  const setActiveEntityType = useNavigationStore((s) => s.setActiveEntityType)
  const setSelectedRow = useNavigationStore((s) => s.setSelectedRow)

  return (
    <div className="rounded-lg border border-surface-200 bg-white">
      <div className="border-b border-surface-200 px-4 py-2.5 text-xs font-semibold uppercase text-surface-500">
        Conversation
      </div>
      <div className="px-4 py-3">
        {conversation ? (
          <div>
            <div className="flex items-center gap-2">
              <FolderOpen size={14} className="shrink-0 text-surface-400" />
              <button
                className="truncate text-sm font-medium text-primary-600 hover:underline"
                onClick={() => {
                  setActiveEntityType('conversation')
                  setSelectedRow(conversation.id, -1)
                  onClose()
                }}
              >
                {conversation.title || 'Untitled'}
              </button>
              <button
                className="shrink-0 text-surface-400 hover:text-surface-600"
                onClick={() => {
                  setActiveEntityType('conversation')
                  setSelectedRow(conversation.id, -1)
                  onClose()
                }}
                title="Open conversation"
              >
                <ExternalLink size={12} />
              </button>
            </div>
            <div className="mt-1 flex items-center gap-2 text-xs text-surface-400">
              {conversation.status && (
                <span className="rounded bg-surface-100 px-1.5 py-0.5 capitalize">
                  {conversation.status}
                </span>
              )}
              <span>{conversation.communication_count} communication{conversation.communication_count !== 1 ? 's' : ''}</span>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-between">
            <span className="text-sm text-surface-400">Not assigned to a conversation</span>
            <button
              className="rounded bg-surface-100 px-2.5 py-1 text-xs font-medium text-surface-500 disabled:opacity-40"
              disabled
              title="Assign conversation (coming soon)"
            >
              Assign
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
