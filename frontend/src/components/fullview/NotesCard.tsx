import { Plus } from 'lucide-react'

interface NotesCardProps {
  notes: unknown[]
}

export function NotesCard({ notes }: NotesCardProps) {
  if (notes.length === 0) return null

  return (
    <div className="rounded-lg border border-surface-200 bg-white">
      <div className="flex items-center justify-between border-b border-surface-200 px-4 py-2.5">
        <span className="text-xs font-semibold uppercase text-surface-500">
          Notes ({notes.length})
        </span>
        <button
          className="flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-surface-500 hover:bg-surface-100 disabled:opacity-40"
          disabled
          title="Add note (coming soon)"
        >
          <Plus size={12} />
          Add
        </button>
      </div>
      <div className="px-4 py-3 text-sm text-surface-400 italic">
        No notes yet
      </div>
    </div>
  )
}
