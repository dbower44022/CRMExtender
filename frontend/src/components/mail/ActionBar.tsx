/** Mail actions (MAIL-27): archive, trash, spam, star, mark unread, for the
 * open thread or the current selection. Each action is applied locally by
 * the server at once and queued to the provider; the queue state shows as
 * pending/failed counts with retry and discard (lib: api/mail.ts).
 */

import { useState } from 'react'
import { Archive, Trash2, ShieldAlert, Star, MailOpen, RotateCcw, X, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { useMailAction, useMailActionQueue, useMailActionResolve, type ThreadSummary } from '../../api/mail.ts'

interface Props {
  /** Threads the actions apply to (the open thread, or the selection). */
  targets: ThreadSummary[]
  /** Message ids per thread key, when the thread detail is loaded (open thread). */
  messageIdsByThread: Record<string, string[]>
  onDone?: () => void
}

function Btn({ title, onClick, disabled, children }: { title: string; onClick: () => void; disabled?: boolean; children: React.ReactNode }) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      disabled={disabled}
      onClick={onClick}
      className="inline-flex h-7 items-center gap-1 rounded px-2 text-xs text-surface-700 hover:bg-surface-100 disabled:opacity-40"
    >
      {children}
    </button>
  )
}

export function ActionBar({ targets, messageIdsByThread, onDone }: Props) {
  const act = useMailAction()
  const queue = useMailActionQueue()
  const resolve = useMailActionResolve()
  const [showQueue, setShowQueue] = useState(false)

  const anyStarred = targets.some((t) => t.starred)
  const anyUnread = targets.some((t) => t.unread_count > 0)
  const disabled = targets.length === 0 || act.isPending

  const run = (action: string, label: string) => {
    // One request per account (an action's targets must share an account).
    const byAccount = new Map<string, string[]>()
    for (const t of targets) {
      const key = `${t.account_id}:${t.thread_id}`
      const ids = messageIdsByThread[key] ?? (t.latest_message_id ? [t.latest_message_id] : [])
      if (ids.length === 0) continue
      byAccount.set(t.account_id, [...(byAccount.get(t.account_id) ?? []), ...ids])
    }
    if (byAccount.size === 0) return
    Promise.all(
      [...byAccount.entries()].map(([account_id, communication_ids]) =>
        act.mutateAsync({ action, account_id, communication_ids }),
      ),
    )
      .then(() => {
        toast.success(`${label}${targets.length > 1 ? ` · ${targets.length} threads` : ''}`)
        onDone?.()
      })
      .catch((err) => toast.error(`${label} failed: ${err instanceof Error ? err.message : String(err)}`))
  }

  const counts = queue.data?.counts ?? { pending: 0, failed: 0 }
  const failed = (queue.data?.items ?? []).filter((i) => i.status === 'failed')

  return (
    <div className="flex items-center gap-1 border-b border-surface-200 bg-surface-0 px-2 py-1">
      <Btn title="Archive (e)" onClick={() => run('archive', 'Archived')} disabled={disabled}><Archive size={14} /> Archive</Btn>
      <Btn title="Trash (#)" onClick={() => run('trash', 'Trashed')} disabled={disabled}><Trash2 size={14} /></Btn>
      <Btn title="Report spam (!)" onClick={() => run('spam', 'Marked as spam')} disabled={disabled}><ShieldAlert size={14} /></Btn>
      <Btn title={anyStarred ? 'Remove star (s)' : 'Star (s)'} onClick={() => run(anyStarred ? 'unstar' : 'star', anyStarred ? 'Unstarred' : 'Starred')} disabled={disabled}>
        <Star size={14} className={anyStarred ? 'fill-amber-400 text-amber-400' : ''} />
      </Btn>
      <Btn title={anyUnread ? 'Mark read' : 'Mark unread (u)'} onClick={() => run(anyUnread ? 'mark_read' : 'mark_unread', anyUnread ? 'Marked read' : 'Marked unread')} disabled={disabled}>
        <MailOpen size={14} />
      </Btn>
      {act.isPending && <Loader2 size={14} className="animate-spin text-surface-400" />}
      <div className="ml-auto flex items-center gap-2 text-xs">
        {counts.pending > 0 && (
          <span className="text-surface-500" title="Queued for the provider; sent on the next sync">
            {counts.pending} pending
          </span>
        )}
        {counts.failed > 0 && (
          <button
            type="button"
            onClick={() => setShowQueue((v) => !v)}
            className="rounded bg-red-50 px-1.5 py-0.5 text-red-700 hover:bg-red-100"
            title="Actions the provider rejected"
          >
            {counts.failed} failed
          </button>
        )}
      </div>
      {showQueue && failed.length > 0 && (
        <div className="absolute right-3 top-12 z-20 w-80 rounded-md border border-surface-200 bg-surface-0 p-2 text-xs shadow-lg">
          <div className="mb-1 font-medium text-surface-700">Failed actions</div>
          <ul className="max-h-64 space-y-1 overflow-y-auto">
            {failed.map((f) => (
              <li key={f.id} className="rounded border border-surface-100 p-1.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{f.action}</span>
                  <span className="text-surface-400">{f.target_ids.length} msg</span>
                </div>
                <div className="truncate text-surface-500" title={f.error ?? ''}>{f.error ?? 'unknown error'}</div>
                <div className="mt-1 flex gap-2">
                  <button type="button" className="inline-flex items-center gap-1 text-primary-700 hover:underline"
                          onClick={() => resolve.mutate({ id: f.id, op: 'retry' })}><RotateCcw size={11} /> Retry</button>
                  <button type="button" className="inline-flex items-center gap-1 text-surface-600 hover:underline"
                          onClick={() => resolve.mutate({ id: f.id, op: 'discard' })}><X size={11} /> Discard and revert</button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
