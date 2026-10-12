/** Mail actions (MAIL-27): archive, trash, spam, star, mark unread, for the
 * open thread or the current selection. Each action is applied locally by
 * the server at once and queued to the provider; the queue state shows as
 * pending/failed counts with retry and discard (lib: api/mail.ts).
 */

import { useState } from 'react'
import { Archive, Trash2, ShieldAlert, Star, MailOpen, RotateCcw, X, Loader2, Clock, AlarmClockOff, Hourglass, BellOff } from 'lucide-react'
import { toast } from 'sonner'
import { threadTargets, useMailAction, useMailActionQueue, useMailActionResolve, useMailAwaitingDismiss, type ThreadSummary } from '../../api/mail.ts'

interface Props {
  /** Threads the actions apply to (the open thread, or the selection). */
  targets: ThreadSummary[]
  onDone?: () => void
  /** Open the snooze picker for the targets (MAIL-28). */
  onSnooze?: () => void
  /** Open a follow-up to the single awaiting-reply target (MAIL-47). */
  onNudge?: (t: ThreadSummary) => void
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

export function ActionBar({ targets, onDone, onSnooze, onNudge }: Props) {
  const act = useMailAction()
  const awaitingOp = useMailAwaitingDismiss()
  const queue = useMailActionQueue()
  const resolve = useMailActionResolve()
  const [showQueue, setShowQueue] = useState(false)

  const anyStarred = targets.some((t) => t.starred)
  const anyUnread = targets.some((t) => t.unread_count > 0)
  const anySnoozed = targets.some((t) => !!t.snoozed_until)
  const awaiting = targets.filter((t) => typeof t.awaiting_days === 'number')
  const disabled = targets.length === 0 || act.isPending

  const run = (action: string, label: string) => {
    if (targets.length === 0) return
    // Whole threads: the server expands each to all of its messages and
    // queues one action per account (D-33).
    act.mutateAsync({ action, threads: targets.flatMap(threadTargets) })
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
      {anySnoozed ? (
        <Btn title="Back to inbox now" onClick={() => run('unsnooze', 'Back in the inbox')} disabled={disabled}><AlarmClockOff size={14} /> Unsnooze</Btn>
      ) : (
        <Btn title="Snooze (z)" onClick={() => onSnooze?.()} disabled={disabled || !onSnooze}><Clock size={14} /> Snooze</Btn>
      )}
      {awaiting.length > 0 && (
        <>
          <Btn title="Follow up: a reply-all to your last message" onClick={() => onNudge?.(awaiting[0])} disabled={awaiting.length !== 1 || !onNudge}>
            <Hourglass size={14} /> Nudge
          </Btn>
          <Btn
            title="Stop waiting for a reply on this thread"
            disabled={awaitingOp.isPending}
            onClick={() =>
              Promise.all(awaiting.map((t) => awaitingOp.mutateAsync({ account_id: t.account_id, thread_id: t.thread_id, op: 'dismiss' })))
                .then(() => { toast.success(`Stopped waiting${awaiting.length > 1 ? ` · ${awaiting.length} threads` : ''}`); onDone?.() })
                .catch((err) => toast.error(err instanceof Error ? err.message : String(err)))
            }
          >
            <BellOff size={14} /> Stop waiting
          </Btn>
        </>
      )}
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
