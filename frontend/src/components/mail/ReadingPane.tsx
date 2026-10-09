/** Reading pane (MAIL-24): the thread's messages, oldest first, with older
 * messages collapsed to one line, the newest unread (or the last) expanded,
 * quoted text folded, and o / Shift+o to expand one or all.
 *
 * Bodies render in sandboxed frames (MAIL-25). Each expanded message has
 * Reply / Reply all / Forward, and the thread ends with the inline
 * composer (MAIL-33).
 */

import { useEffect, useMemo, useState } from 'react'
import { ChevronDown, ChevronRight, Download, Forward, Paperclip, Reply, ReplyAll } from 'lucide-react'
import { toast } from 'sonner'
import { useMailAction, useThread, type MailAttachment, type MailMessage } from '../../api/mail.ts'
import { useSystemSettings } from '../../api/settings.ts'
import { splitEmailZones } from '../../lib/emailZones.ts'
import { useComposeStore, type ComposeMode } from '../../stores/compose.ts'
import { MessageFrame } from './MessageFrame.tsx'
import { ContextColumn } from './ContextColumn.tsx'
import { InlineReply } from '../compose/InlineReply.tsx'

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

const PREVIEWABLE = /^(image\/(png|jpeg|gif|webp)|application\/pdf|text\/plain)$/i

function fmtSize(n: number | null): string {
  if (!n) return ''
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

/** Inline images already appear in the body via cid:; keep them out of the chip row. */
function isInlineImage(a: MailAttachment, html: string): boolean {
  return !!a.content_id && !!a.is_inline && html.includes(`cid:${a.content_id}`)
}

function AttachmentChip({ attachment: a }: { attachment: MailAttachment }) {
  const url = `/api/v1/mail/attachments/${encodeURIComponent(a.id)}`
  const previewable = PREVIEWABLE.test(a.mime_type || '')
  return (
    <span className="inline-flex items-center overflow-hidden rounded border border-surface-200">
      <a
        href={previewable ? url : `${url}?download=1`}
        target={previewable ? '_blank' : undefined}
        rel="noopener noreferrer"
        className="inline-flex max-w-[260px] items-center gap-1 px-1.5 py-0.5 hover:bg-surface-100"
        title={previewable ? 'Open in a new tab' : 'Download'}
      >
        <Paperclip size={11} className="shrink-0" />
        <span className="truncate">{a.filename}</span>
        {a.size_bytes ? <span className="shrink-0 text-surface-400">{fmtSize(a.size_bytes)}</span> : null}
      </a>
      <a
        href={`${url}?download=1`}
        className="border-l border-surface-200 px-1.5 py-0.5 text-surface-500 hover:bg-surface-100"
        title="Download"
        aria-label={`Download ${a.filename}`}
      >
        <Download size={11} />
      </a>
    </span>
  )
}

/** Which messages start expanded: every unread one, plus the last. */
function initialExpanded(messages: MailMessage[]): Set<string> {
  const ids = new Set<string>()
  for (const m of messages) if (!m.is_read) ids.add(m.id)
  const last = messages[messages.length - 1]
  if (last) ids.add(last.id)
  return ids
}

function MessageBody({ html, text, sender, messageId }: { html: string; text: string; sender: string | null; messageId: string }) {
  const cidBase = `/api/v1/mail/attachments/cid/${encodeURIComponent(messageId)}/`
  const [showQuoted, setShowQuoted] = useState(false)
  // Split before sanitizing: the splitter looks for client markup the
  // sanitizer may rewrite. Each zone then renders in its own sandboxed frame.
  const zones = useMemo(() => (html ? splitEmailZones(html) : null), [html])
  if (!zones) {
    return <pre className="mt-3 whitespace-pre-wrap font-sans text-sm text-surface-800">{text}</pre>
  }
  return (
    <div className="mt-3">
      <MessageFrame html={zones.primaryHtml} senderAddress={sender} cidBase={cidBase} />
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
            <MessageFrame html={zones.quotedHtml} senderAddress={sender} cidBase={cidBase} className="mt-2 border-l-2 border-surface-200 pl-3" />
          )}
        </div>
      )}
    </div>
  )
}

export function ReadingPane({ accountId, threadId }: Props) {
  const thread = useThread(accountId, threadId)
  const { data: settings } = useSystemSettings()
  const markRead = useMailAction()
  const openCompose = useComposeStore((s) => s.openCompose)

  // Mark the thread's unread messages read after the dwell (MAIL-27, PRD §5.1).
  const dwellMs = Number(settings?.mail_mark_read_dwell_ms ?? '1500')
  const unreadIds = thread.data?.messages.filter((m) => !m.is_read).map((m) => m.id) ?? []
  const unreadKey = unreadIds.join(',')
  const mutate = markRead.mutate
  const loadedAccount = thread.data?.account_id
  useEffect(() => {
    if (!loadedAccount || !unreadKey || !(dwellMs >= 0) || settings?.mail_mark_read_dwell_ms === '0') return
    const ids = unreadKey.split(',')
    const timer = window.setTimeout(() => {
      mutate({ action: 'mark_read', account_id: loadedAccount, communication_ids: ids })
    }, dwellMs)
    return () => window.clearTimeout(timer)
  }, [loadedAccount, unreadKey, dwellMs, settings?.mail_mark_read_dwell_ms, mutate])
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
  const tKey = `${t.account_id}:${t.thread_id}`
  const replyTo = (mode: ComposeMode, messageId: string) => {
    if (openCompose(mode, { communicationId: messageId, threadKey: tKey }, 'inline') === null) toast.info('Close a composer first (three are open)')
  }
  return (
    <div className="flex h-full overflow-hidden">
    <div className="flex min-w-0 flex-1 flex-col overflow-hidden outline-none" tabIndex={0} onKeyDown={onKeyDown}>
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
                  <div className="mt-1 flex gap-1 pl-5 text-xs text-surface-500">
                    <button type="button" onClick={() => replyTo('reply', m.id)} className="inline-flex items-center gap-1 rounded px-1 py-0.5 hover:bg-surface-100 hover:text-surface-800" title="Reply to this message"><Reply size={12} /> Reply</button>
                    <button type="button" onClick={() => replyTo('reply_all', m.id)} className="inline-flex items-center gap-1 rounded px-1 py-0.5 hover:bg-surface-100 hover:text-surface-800" title="Reply all to this message"><ReplyAll size={12} /> Reply all</button>
                    <button type="button" onClick={() => replyTo('forward', m.id)} className="inline-flex items-center gap-1 rounded px-1 py-0.5 hover:bg-surface-100 hover:text-surface-800" title="Forward this message"><Forward size={12} /> Forward</button>
                  </div>
                  {m.attachments.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1 pl-5 text-xs text-surface-600">
                      {m.attachments.filter((a) => !isInlineImage(a, m.body_html)).map((a) => (
                        <AttachmentChip key={a.id} attachment={a} />
                      ))}
                    </div>
                  )}
                  <div className="pl-5">
                    <MessageBody html={m.body_html} text={m.body_text} sender={m.sender.address} messageId={m.id} />
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
        {t.messages.length > 0 && <InlineReply threadKey={tKey} lastMessageId={t.messages[t.messages.length - 1].id} />}
      </div>
    </div>
    <ContextColumn thread={t} />
    </div>
  )
}
