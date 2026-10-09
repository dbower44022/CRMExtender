/** Reading pane (MAIL-24): the thread's messages, oldest first, with older
 * messages collapsed to one line, the newest unread (or the last) expanded,
 * quoted text folded, and o / Shift+o to expand one or all.
 *
 * Bodies still render through the regex sanitizer here; MAIL-25 moves
 * them into a sandboxed frame.
 */

import { useMemo, useState } from 'react'
import { ChevronDown, ChevronRight, Paperclip } from 'lucide-react'
import { useThread, type MailMessage } from '../../api/mail.ts'
import { sanitizeHtml } from '../../lib/sanitizeHtml.ts'
import { splitEmailZones } from '../../lib/emailZones.ts'

interface Props {
  accountId: string | null
  threadId: string | null
}

function fmt(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
}

function senderLabel(m: MailMessage): string {
  if (m.sender.is_me) return 'me'
  return m.sender.contact_name || m.sender.name || m.sender.address || '(unknown)'
}

/** Which messages start expanded: every unread one, plus the last. */
function initialExpanded(messages: MailMessage[]): Set<string> {
  const ids = new Set<string>()
  for (const m of messages) if (!m.is_read) ids.add(m.id)
  const last = messages[messages.length - 1]
  if (last) ids.add(last.id)
  return ids
}

function MessageBody({ html, text }: { html: string; text: string }) {
  const [showQuoted, setShowQuoted] = useState(false)
  const zones = useMemo(() => (html ? splitEmailZones(sanitizeHtml(html)) : null), [html])
  if (!zones) {
    return <pre className="mt-3 whitespace-pre-wrap font-sans text-sm text-surface-800">{text}</pre>
  }
  return (
    <div className="mt-3">
      <div
        className="prose prose-sm max-w-none overflow-x-auto text-surface-800"
        dangerouslySetInnerHTML={{ __html: zones.primaryHtml }}
      />
      {zones.quotedHtml && (
        <div className="mt-2">
          <button
            type="button"
            onClick={() => setShowQuoted((v) => !v)}
            className="rounded border border-surface-200 px-2 py-0.5 text-xs text-surface-500 hover:bg-surface-100"
            title={showQuoted ? 'Hide quoted text' : 'Show quoted text'}
          >
            {showQuoted ? '· · · hide quoted text' : '· · ·'}
          </button>
          {showQuoted && (
            <div
              className="prose prose-sm mt-2 max-w-none border-l-2 border-surface-200 pl-3 text-surface-600"
              dangerouslySetInnerHTML={{ __html: zones.quotedHtml }}
            />
          )}
        </div>
      )}
    </div>
  )
}

export function ReadingPane({ accountId, threadId }: Props) {
  const thread = useThread(accountId, threadId)
  // Expanded set keyed by the loaded thread: a new thread starts from
  // initialExpanded() without a seeding effect.
  const loadedKey = thread.data ? `${thread.data.account_id}:${thread.data.thread_id}` : null
  const [exp, setExp] = useState<{ key: string | null; ids: Set<string> } | null>(null)
  const expanded = useMemo(
    () => (exp && exp.key === loadedKey ? exp.ids : initialExpanded(thread.data?.messages ?? [])),
    [exp, loadedKey, thread.data],
  )
  const setExpanded = (update: Set<string> | ((prev: Set<string>) => Set<string>)) =>
    setExp({ key: loadedKey, ids: typeof update === 'function' ? update(expanded) : update })

  const toggle = (id: string) =>
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const onKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (!thread.data || e.altKey || e.ctrlKey || e.metaKey) return
    if (e.key === 'O') {
      e.preventDefault()
      const all = thread.data.messages.map((m) => m.id)
      setExpanded((prev) => (prev.size === all.length ? new Set([all[all.length - 1]]) : new Set(all)))
    }
  }

  if (!threadId) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-surface-400">
        Select a thread to read it.
      </div>
    )
  }
  if (thread.isLoading) return <div className="p-4 text-sm text-surface-500">Loading…</div>
  if (thread.error || !thread.data) return <div className="p-4 text-sm text-red-700">Could not load this thread.</div>

  const t = thread.data
  return (
    <div className="flex h-full flex-col overflow-hidden outline-none" tabIndex={0} onKeyDown={onKeyDown}>
      <header className="border-b border-surface-200 px-5 py-3">
        <h1 className="truncate text-base font-semibold text-surface-900">{t.subject}</h1>
        <div className="mt-0.5 flex flex-wrap items-center gap-1 text-xs text-surface-500">
          <span>{t.message_count} message{t.message_count === 1 ? '' : 's'}</span>
          <span>·</span>
          <span>{t.account_email}</span>
          {t.labels.map((l) => (
            <span key={l} className="rounded bg-surface-100 px-1 text-[11px] text-surface-600">{l}</span>
          ))}
          {t.message_count > 1 && (
            <button
              type="button"
              onClick={() => setExpanded(new Set(t.messages.map((m) => m.id)))}
              className="ml-auto rounded px-1.5 py-0.5 text-[11px] text-primary-700 hover:bg-primary-50"
              title="Expand all (Shift+O)"
            >
              Expand all
            </button>
          )}
        </div>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {t.messages.map((m) => {
          const isOpen = expanded.has(m.id)
          const toLine = m.participants.filter((p) => p.role === 'to').map((p) => p.name || p.address).join(', ')
          return (
            <article key={m.id} className={`border-b border-surface-100 ${isOpen ? 'px-5 py-4' : ''}`}>
              {isOpen ? (
                <>
                  <div className="flex items-baseline justify-between gap-3">
                    <div className="min-w-0">
                      <button
                        type="button"
                        onClick={() => toggle(m.id)}
                        className="inline-flex items-center gap-1 text-left"
                        title="Collapse"
                      >
                        <ChevronDown size={14} className="text-surface-400" />
                        <span className={`font-medium ${m.is_read ? 'text-surface-900' : 'text-primary-800'}`}>{senderLabel(m)}</span>
                      </button>
                      {!m.sender.is_me && m.sender.address && (
                        <span className="ml-1 text-xs text-surface-500">&lt;{m.sender.address}&gt;</span>
                      )}
                      <div className="truncate pl-5 text-xs text-surface-500">to {toLine || '—'}</div>
                    </div>
                    <span className="shrink-0 text-xs text-surface-500">{fmt(m.timestamp)}</span>
                  </div>
                  {m.attachments.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1 pl-5 text-xs text-surface-600">
                      {m.attachments.map((a) => (
                        <span key={a.id} className="inline-flex items-center gap-1 rounded border border-surface-200 px-1.5 py-0.5">
                          <Paperclip size={11} /> {a.filename}
                        </span>
                      ))}
                    </div>
                  )}
                  <div className="pl-5">
                    <MessageBody html={m.body_html} text={m.body_text} />
                  </div>
                </>
              ) : (
                <button
                  type="button"
                  onClick={() => toggle(m.id)}
                  className="flex w-full items-center gap-2 px-5 py-2 text-left hover:bg-surface-50"
                  title="Expand (o)"
                >
                  <ChevronRight size={14} className="shrink-0 text-surface-400" />
                  <span className={`w-40 shrink-0 truncate text-sm ${m.is_read ? 'text-surface-700' : 'font-semibold text-surface-900'}`}>
                    {senderLabel(m)}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-xs text-surface-500">{m.snippet}</span>
                  {m.attachments.length > 0 && <Paperclip size={12} className="shrink-0 text-surface-400" />}
                  <span className="shrink-0 text-xs text-surface-500">{fmt(m.timestamp)}</span>
                </button>
              )}
            </article>
          )
        })}
      </div>
    </div>
  )
}
