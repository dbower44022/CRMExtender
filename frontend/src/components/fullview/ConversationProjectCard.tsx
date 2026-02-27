import { FolderOpen } from 'lucide-react'
import type { ConversationTopic } from '../../types/api.ts'

interface ConversationProjectCardProps {
  topic: ConversationTopic | null
}

export function ConversationProjectCard({ topic }: ConversationProjectCardProps) {
  return (
    <div className="rounded-lg border border-surface-200 bg-white">
      <div className="flex items-center gap-2 border-b border-surface-200 px-4 py-2.5">
        <FolderOpen size={14} className="text-surface-400" />
        <span className="text-xs font-semibold uppercase text-surface-500">
          Topic / Project
        </span>
      </div>
      <div className="px-4 py-3">
        {topic ? (
          <div>
            <div className="text-sm font-medium text-surface-800">{topic.name}</div>
            {topic.project_name && (
              <div className="mt-0.5 text-xs text-surface-400">
                Project: {topic.project_name}
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-between">
            <span className="text-sm text-surface-400">Not assigned to a topic</span>
            <button
              className="rounded bg-surface-100 px-2.5 py-1 text-xs font-medium text-surface-500 disabled:opacity-40"
              disabled
              title="Assign topic (coming soon)"
            >
              Assign
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
