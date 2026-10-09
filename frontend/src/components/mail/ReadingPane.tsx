/** Reading pane: the selected thread's messages, oldest first.
 *
 * First cut for MAIL-21: every message expanded, body rendered through
 * the existing sanitizer. MAIL-24 adds collapsing and quoted-text
 * folding; MAIL-25 moves rendering into a sandboxed frame.
 */

import { useThread } from '../../api/mail.ts'
import { sanitizeHtml } from '../../lib/sanitizeHtml.ts'

interface Props {
  accountId: string | null
  threadId: string | null
}

function fmt(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
}

export function ReadingPane({ accountId, threadId }: Props) {
  const thread = useThread(accountId, threadId)

  if (!threadId) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-surface-400">
        Select a thread to read it.
      </div>
    )
  }
  if (thread.isLoading) {
    return <div className="p-4 text-sm text-surface-500">Loading…</div>
  }
  if (thread.error || !thread.data) {
    return <div className="p-4 text-sm text-red-700">Could not load this thread.</div>
  }
  const t = thread.data
  return (
    <div className="flex h-full flex-col overflow-hidden">
      <header className="border-b border-surface-200 px-5 py-3">
        <h1 className="truncate text-base font-semibold text-surface-900">{t.subject}</h1>
        <div className="mt-0.5 flex flex-wrap gap-1 text-xs text-surface-500">
          <span>{t.message_count} message{t.message_count === 1 ? '' : 's'}</span>
          <span>·</span>
          <span>{t.account_email}</span>
          {t.labels.map((l) => (
            <span key={l} className="rounded bg-surface-100 px-1 text-[11px] text-surface-600">{l}</span>
          ))}
        </div>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {t.messages.map((m) => (
          <article key={m.id} className="border-b border-surface-100 px-5 py-4">
            <div className="flex items-baseline justify-between gap-3">
              <div className="min-w-0">
                <span className="font-medium text-surface-900">
                  {m.sender.is_me ? 'me' : m.sender.contact_name || m.sender.name || m.sender.address}
                </span>
                {!m.sender.is_me && m.sender.address && (
                  <span className="ml-1 text-xs text-surface-500">&lt;{m.sender.address}&gt;</span>
                )}
                <div className="truncate text-xs text-surface-500">
                  to {m.participants.filter((p) => p.role === 'to').map((p) => p.name || p.address).join(', ') || '—'}
                </div>
              </div>
              <span className="shrink-0 text-xs text-surface-500">{fmt(m.timestamp)}</span>
            </div>
            {m.attachments.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1 text-xs text-surface-600">
                {m.attachments.map((a) => (
                  <span key={a.id} className="rounded border border-surface-200 px-1.5 py-0.5">{a.filename}</span>
                ))}
              </div>
            )}
            {m.body_html ? (
              <div
                className="prose prose-sm mt-3 max-w-none overflow-x-auto text-surface-800"
                dangerouslySetInnerHTML={{ __html: sanitizeHtml(m.body_html) }}
              />
            ) : (
              <pre className="mt-3 whitespace-pre-wrap font-sans text-sm text-surface-800">{m.body_text}</pre>
            )}
          </article>
        ))}
      </div>
    </div>
  )
}
