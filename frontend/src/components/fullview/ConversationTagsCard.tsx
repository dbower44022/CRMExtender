import { Tag } from 'lucide-react'
import type { ConversationTag } from '../../types/api.ts'

interface ConversationTagsCardProps {
  tags: ConversationTag[]
}

export function ConversationTagsCard({ tags }: ConversationTagsCardProps) {
  if (tags.length === 0) return null

  return (
    <div className="rounded-lg border border-surface-200 bg-white">
      <div className="flex items-center gap-2 border-b border-surface-200 px-4 py-2.5">
        <Tag size={14} className="text-surface-400" />
        <span className="text-xs font-semibold uppercase text-surface-500">
          Tags ({tags.length})
        </span>
      </div>
      <div className="px-4 py-3">
        <div className="flex flex-wrap gap-1.5">
          {tags.map((t) => (
            <span
              key={t.id}
              className="inline-flex items-center gap-1 rounded-full bg-surface-100 px-2.5 py-0.5 text-xs text-surface-600"
            >
              {t.name}
              {t.source === 'ai' && (
                <span className="rounded bg-surface-200 px-1 text-[10px] text-surface-400">
                  ai
                </span>
              )}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
