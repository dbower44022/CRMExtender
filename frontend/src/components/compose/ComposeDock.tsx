/** Docked composers (MAIL-34) and the undo-send bar (MAIL-35).
 *
 * Up to three composers sit along the bottom right, each minimizable to a
 * title tab. An inline composer whose thread is not on screen shows here as
 * a tab too, and goes back inline when its thread is reopened. Messages in
 * their undo window, and scheduled ones, show a bar with Undo.
 */

import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Clock, Minus, Square, X } from 'lucide-react'
import { toast } from 'sonner'
import { useComposeStore, type Composer, type PendingSend } from '../../stores/compose.ts'
import { useNavigationStore } from '../../stores/navigation.ts'
import { useUndoSend, type OutboundDraft } from '../../api/outbound.ts'
import { get } from '../../api/client.ts'
import { isInlineVisible, modeLabel, secondsLeft } from '../../lib/composeUi.ts'
import { ComposeFormLoader } from './ComposeForm.tsx'

function DockedComposer({ composer }: { composer: Composer }) {
  const closeCompose = useComposeStore((s) => s.closeCompose)
  const setMinimized = useComposeStore((s) => s.setMinimized)
  const title = modeLabel(composer.mode) + (composer.resume?.subject ? ` · ${composer.resume.subject}` : '')
  const header = (
    <div className="flex items-center justify-between gap-2 rounded-t-lg bg-surface-800 px-3 py-1.5 text-white">
      <button type="button" className="min-w-0 flex-1 truncate text-left text-sm font-medium" onClick={() => setMinimized(composer.id, !composer.minimized)} title={composer.minimized ? 'Open' : 'Minimize'}>
        {title}
      </button>
      <button type="button" aria-label={composer.minimized ? 'Open composer' : 'Minimize composer'} className="rounded p-0.5 hover:bg-white/20" onClick={() => setMinimized(composer.id, !composer.minimized)}>
        {composer.minimized ? <Square size={12} /> : <Minus size={14} />}
      </button>
      <button type="button" aria-label="Close composer" className="rounded p-0.5 hover:bg-white/20" onClick={() => closeCompose(composer.id)}>
        <X size={14} />
      </button>
    </div>
  )
  if (composer.minimized) {
    return <div className="w-64 rounded-t-lg shadow-lg" data-testid="composer-minimized">{header}</div>
  }
  return (
    <div className="flex h-[600px] max-h-[85vh] w-[560px] max-w-[95vw] flex-col rounded-t-lg border border-surface-200 bg-white shadow-2xl" data-testid="composer-open">
      {header}
      <ComposeFormLoader composer={composer} variant="dock" onClose={() => closeCompose(composer.id)} />
    </div>
  )
}

function PendingSendBar({ p }: { p: PendingSend }) {
  const removePendingSend = useComposeStore((s) => s.removePendingSend)
  const resumeDraft = useComposeStore((s) => s.resumeDraft)
  const undo = useUndoSend()
  const qc = useQueryClient()
  const [now, setNow] = useState(() => Date.now())
  const left = secondsLeft(p.sendAt, now)

  // Tick once a second; an undo-window send leaves the bar when its time passes.
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(t)
  }, [])
  useEffect(() => {
    if (p.scheduled || left > 0) return
    const t = window.setTimeout(() => { removePendingSend(p.draftId); qc.invalidateQueries({ queryKey: ['mail'] }) }, 1500)
    return () => window.clearTimeout(t)
  }, [left, p.scheduled, p.draftId, removePendingSend, qc])

  const onUndo = async () => {
    try {
      await undo.mutateAsync(p.draftId)
      removePendingSend(p.draftId)
      const draft = await get<OutboundDraft>(`/outbound-emails/${encodeURIComponent(p.draftId)}`)
      if (resumeDraft(draft) === null) toast.info('Draft kept — close a composer to open it')
    } catch {
      removePendingSend(p.draftId)
      toast.error('Too late — the message has already been sent')
      qc.invalidateQueries({ queryKey: ['mail'] })
    }
  }

  const label = p.scheduled
    ? `Scheduled for ${new Date(p.sendAt).toLocaleString([], { weekday: 'short', hour: 'numeric', minute: '2-digit' })}`
    : left > 0 ? `Sending in ${left}s` : 'Sent'
  return (
    <div className="flex items-center gap-3 rounded-lg bg-surface-800 px-3 py-2 text-sm text-white shadow-lg" role="status">
      <Clock size={14} className="shrink-0 text-surface-300" />
      <span className="min-w-0 flex-1 truncate">{label} · {p.subject || '(no subject)'}</span>
      {(p.scheduled || left > 0) && (
        <button type="button" onClick={onUndo} disabled={undo.isPending} className="rounded bg-white/15 px-2 py-0.5 text-xs font-semibold hover:bg-white/25 disabled:opacity-50">
          {p.scheduled ? 'Cancel' : 'Undo'}
        </button>
      )}
    </div>
  )
}

export function ComposeDock() {
  const composers = useComposeStore((s) => s.composers)
  const pending = useComposeStore((s) => s.pendingSends)
  const mailMode = useNavigationStore((s) => s.mailMode)
  const threadId = useNavigationStore((s) => s.mailThreadId)
  const docked = composers.filter((c) => !isInlineVisible(c, mailMode, threadId))
  if (docked.length === 0 && pending.length === 0) return null
  return (
    <div className="pointer-events-none fixed bottom-0 right-4 z-40 flex flex-col items-end gap-2">
      <div className="pointer-events-auto flex flex-col items-end gap-1">
        {pending.map((p) => <PendingSendBar key={p.draftId} p={p} />)}
      </div>
      <div className="pointer-events-auto flex items-end gap-2">
        {docked.map((c) => (
          c.placement === 'inline'
            ? <InlineAsTab key={c.id} composer={c} />
            : <DockedComposer key={c.id} composer={c} />
        ))}
      </div>
    </div>
  )
}

/** An inline reply whose thread is off screen: a tab that closes it or jumps back. */
function InlineAsTab({ composer }: { composer: Composer }) {
  const closeCompose = useComposeStore((s) => s.closeCompose)
  const openMail = useNavigationStore((s) => s.openMail)
  const key = composer.context?.threadKey ?? ''
  const [acct, thread] = key.includes(':') ? [key.slice(0, key.indexOf(':')), key.slice(key.indexOf(':') + 1)] : ['unified', null]
  return (
    <div className="flex w-64 items-center justify-between gap-2 rounded-t-lg bg-surface-800 px-3 py-1.5 text-white shadow-lg" data-testid="composer-minimized">
      <button type="button" className="min-w-0 flex-1 truncate text-left text-sm font-medium" title="Back to the thread"
        onClick={() => openMail(acct, 'inbox', thread)}>
        {modeLabel(composer.mode)} · in thread
      </button>
      <button type="button" aria-label="Close composer" className="rounded p-0.5 hover:bg-white/20" onClick={() => closeCompose(composer.id)}>
        <X size={14} />
      </button>
    </div>
  )
}
