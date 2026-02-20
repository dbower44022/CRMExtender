import { format, parseISO } from 'date-fns'
import { Mail, MessageSquare, Calendar, StickyNote } from 'lucide-react'
import type { TimelineEntry } from '../../types/api.ts'

const TYPE_ICONS: Record<string, typeof Mail> = {
  communication: Mail,
  conversation: MessageSquare,
  event: Calendar,
  note: StickyNote,
}

const TYPE_COLORS: Record<string, string> = {
  communication: 'bg-blue-50 text-blue-500',
  conversation: 'bg-purple-50 text-purple-500',
  event: 'bg-green-50 text-green-500',
  note: 'bg-amber-50 text-amber-500',
}

interface TimelineZoneProps {
  entries: TimelineEntry[]
}

export function TimelineZone({ entries }: TimelineZoneProps) {
  if (!entries || entries.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center p-4 text-sm text-surface-400">
        No activity yet
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <h4 className="border-b border-surface-200 px-4 py-2 text-xs font-semibold text-surface-500 uppercase">
        Activity
      </h4>
      <div className="flex-1 overflow-y-auto">
        <div className="space-y-0">
          {entries.map((entry) => {
            const Icon = TYPE_ICONS[entry.type] ?? Mail
            const color = TYPE_COLORS[entry.type] ?? 'bg-surface-50 text-surface-500'
            let dateStr = ''
            try {
              dateStr = format(parseISO(entry.date), 'MMM d, yyyy')
            } catch {
              dateStr = entry.date
            }

            return (
              <div
                key={`${entry.type}-${entry.id}`}
                className="flex gap-3 border-b border-surface-100 px-4 py-2.5"
              >
                <div
                  className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md ${color}`}
                >
                  <Icon size={13} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-surface-800">
                    {entry.title}
                  </p>
                  {entry.summary && (
                    <p className="mt-0.5 line-clamp-2 text-xs text-surface-500">
                      {entry.summary}
                    </p>
                  )}
                </div>
                <span className="shrink-0 text-xs text-surface-400">
                  {dateStr}
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
