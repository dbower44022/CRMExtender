/** Thread list rows for the selected folder.
 *
 * First cut for MAIL-21: plain rows with unread weight, account chip,
 * star and attachment marks. MAIL-23 adds virtualization, selection, and
 * the keyboard model.
 */

import { Paperclip, Star } from 'lucide-react'
import type { ThreadPage, ThreadSummary } from '../../api/mail.ts'

interface Props {
  page: ThreadPage | undefined
  loading: boolean
  error: string | null
  selectedThreadId: string | null
  unified: boolean
  onSelect: (t: ThreadSummary) => void
}

function fmtDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const now = new Date()
  const sameDay = d.toDateString() === now.toDateString()
  if (sameDay) return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
  const sameYear = d.getFullYear() === now.getFullYear()
  return d.toLocaleDateString([], sameYear ? { month: 'short', day: 'numeric' } : { year: '2-digit', month: 'short', day: 'numeric' })
}

function participantsLine(t: ThreadSummary): string {
  const names = t.participants.map((p) => (p.is_me ? 'me' : p.name?.split(' ')[0] || p.address.split('@')[0]))
  const line = names.slice(0, 3).join(', ')
  return t.message_count > 1 ? `${line} (${t.message_count})` : line
}

function accountChip(email: string): string {
  const local = email.split('@')[0]
  const domain = email.split('@')[1] ?? ''
  return domain.split('.')[0] || local
}

export function ThreadList({ page, loading, error, selectedThreadId, unified, onSelect }: Props) {
  if (error) {
    return <div className="p-3 text-sm text-red-700">Could not load threads: {error}</div>
  }
  if (loading && !page) {
    return <div className="p-3 text-sm text-surface-500">Loading…</div>
  }
  if (!page || page.items.length === 0) {
    return <div className="p-3 text-sm text-surface-500">Nothing here.</div>
  }
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-surface-200 px-3 py-1.5 text-xs text-surface-500">
        {page.total} thread{page.total === 1 ? '' : 's'}
        {page.total > page.items.length ? ` · showing first ${page.items.length}` : ''}
      </div>
      <ul className="min-h-0 flex-1 overflow-y-auto">
        {page.items.map((t) => {
          const unread = t.unread_count > 0
          const active = t.thread_id === selectedThreadId
          return (
            <li key={`${t.account_id}:${t.thread_id}`}>
              <button
                onClick={() => onSelect(t)}
                className={`block w-full border-b border-surface-100 px-3 py-2 text-left ${
                  active ? 'bg-primary-50' : 'hover:bg-surface-50'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className={`min-w-0 flex-1 truncate text-sm ${unread ? 'font-semibold text-surface-900' : 'text-surface-700'}`}>
                    {participantsLine(t)}
                  </span>
                  {unified && (
                    <span className="rounded bg-surface-100 px-1 text-[10px] uppercase tracking-wide text-surface-500" title={t.account_email}>
                      {accountChip(t.account_email)}
                    </span>
                  )}
                  <span className="shrink-0 text-xs text-surface-500">{fmtDate(t.last_at)}</span>
                </div>
                <div className="mt-0.5 flex items-center gap-1.5">
                  <span className={`min-w-0 flex-1 truncate text-sm ${unread ? 'font-medium text-surface-900' : 'text-surface-700'}`}>
                    {t.subject}
                  </span>
                  {t.has_attachments && <Paperclip size={12} className="shrink-0 text-surface-400" />}
                  {t.starred && <Star size={12} className="shrink-0 fill-amber-400 text-amber-400" />}
                </div>
                <div className="mt-0.5 truncate text-xs text-surface-500">{t.snippet}</div>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
