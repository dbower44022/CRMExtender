import { Pin, Plus } from 'lucide-react'
import { formatTimestamp } from '../../lib/formatTimestamp.ts'
import type { ConversationNote } from '../../types/api.ts'

interface ConversationNotesCardProps {
  notes: ConversationNote[]
}

export function ConversationNotesCard({ notes }: ConversationNotesCardProps) {
  return (
    <div className="rounded-lg border border-surface-200 bg-white">
      <div className="flex items-center justify-between border-b border-surface-200 px-4 py-2.5">
        <span className="text-xs font-semibold uppercase text-surface-500">
          Notes ({notes.length})
        </span>
        <button
          disabled
          className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs text-surface-300"
          title="Add note (coming soon)"
        >
          <Plus size={12} />
          Add
        </button>
      </div>
      {notes.length === 0 ? (
        <div className="px-4 py-4 text-center text-xs text-surface-400">
          No notes yet.
        </div>
      ) : (
        <div className="divide-y divide-surface-100">
          {notes.map((n) => (
            <div key={n.id} className="px-4 py-2.5">
              <div className="flex items-center gap-2">
                {n.is_pinned && <Pin size={12} className="shrink-0 text-amber-500" />}
                <span className="truncate text-sm font-medium text-surface-800">
                  {n.title || 'Untitled Note'}
                </span>
                <span className="ml-auto shrink-0 text-xs text-surface-400">
                  {formatTimestamp(n.updated_at)}
                </span>
              </div>
              {n.content_preview && (
                <div className="mt-0.5 line-clamp-2 text-xs text-surface-500">
                  {n.content_preview}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
