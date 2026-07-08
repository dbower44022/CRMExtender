import { useState } from 'react'
import { Pin, Plus } from 'lucide-react'
import { formatTimestamp } from '../../lib/formatTimestamp.ts'
import { useEntityNotes, type Note } from '../../api/notes.ts'
import { NoteModal } from './NoteModal.tsx'

interface EntityNotesCardProps {
  entityType: string
  entityId: string
}

/** Self-contained notes card: list, create, open/edit (UI Migration Phase 3).
 *
 * Always rendered (with an empty state) so "Add" is reachable — supersedes
 * the earlier suppress-when-empty behavior, which predated note creation
 * in the SPA.
 */
export function EntityNotesCard({ entityType, entityId }: EntityNotesCardProps) {
  const { data } = useEntityNotes(entityType, entityId)
  const [editing, setEditing] = useState<Note | null | 'new'>(null)

  const notes = data?.notes ?? []

  return (
    <div className="rounded-lg border border-surface-200 bg-white">
      <div className="flex items-center justify-between border-b border-surface-200 px-4 py-2.5">
        <span className="text-xs font-semibold uppercase text-surface-500">
          Notes{notes.length > 0 && ` (${notes.length})`}
        </span>
        <button
          onClick={() => setEditing('new')}
          className="flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-primary-600 hover:bg-primary-50"
        >
          <Plus size={12} />
          Add
        </button>
      </div>

      {notes.length === 0 ? (
        <div className="px-4 py-3 text-sm italic text-surface-400">
          No notes yet
        </div>
      ) : (
        <div className="divide-y divide-surface-100">
          {notes.map((n) => (
            <button
              key={n.id}
              onClick={() => setEditing(n)}
              className="block w-full px-4 py-2.5 text-left transition-colors hover:bg-surface-50"
            >
              <div className="flex items-center gap-2">
                {!!n.is_pinned && (
                  <Pin size={12} className="shrink-0 text-amber-500" />
                )}
                <span className="truncate text-sm font-medium text-surface-800">
                  {n.title || 'Untitled Note'}
                </span>
                <span className="ml-auto shrink-0 text-xs text-surface-400">
                  {n.author_name ? `${n.author_name} · ` : ''}
                  {formatTimestamp(n.updated_at)}
                </span>
              </div>
              {n.content_html && (
                <div className="mt-0.5 line-clamp-2 text-xs text-surface-500">
                  {stripHtml(n.content_html)}
                </div>
              )}
            </button>
          ))}
        </div>
      )}

      {editing !== null && (
        <NoteModal
          entityType={entityType}
          entityId={entityId}
          note={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  )
}

function stripHtml(html: string): string {
  const div = document.createElement('div')
  div.innerHTML = html
  return div.textContent || ''
}
