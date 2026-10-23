/** The composer form shared by the dock and the inline reply (MAIL-33/34/35).
 *
 * `ComposeFormLoader` gathers what the form starts from — the reply or
 * forward context, a resumed draft, or nothing — and mounts `ComposeForm`
 * once it is known, so the form seeds its state from props and needs no
 * pre-fill effects. The form owns recipients, subject, body, attachments,
 * autosave, and the three ways to send: now (with the undo window),
 * scheduled, or immediately.
 */

import { useEffect, useRef, useState, type DragEvent } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { CalendarClock, ChevronDown, ChevronRight, Loader2, Paperclip, Save, Send, X } from 'lucide-react'
import { toast } from 'sonner'
import { useComposeStore, type Composer } from '../../stores/compose.ts'
import { useAccounts, useSystemSettings } from '../../api/settings.ts'
import {
  useComposeContext, useCreateDraft, useDraftAttachments, useRemoveDraftAttachment, useSendEmail,
  useSignatures, useUpdateDraft, uploadDraftAttachments, type OutboundDraft, type Recipient, type SendOptions,
} from '../../api/outbound.ts'
import { RecipientField } from './RecipientField.tsx'
import { SendingAccountSelector } from './SendingAccountSelector.tsx'
import { RichTextEditor } from '../editor/RichTextEditor.tsx'
import { defaultSignature, fmtBytes, scheduleOptions } from '../../lib/composeUi.ts'

const AUTO_SAVE_INTERVAL = 30_000

export interface ReplyHeaders {
  conversation_id: string | null
  reply_to_communication_id: string | null
  forward_of_communication_id: string | null
}

export interface ComposeInitial {
  fromAccountId: string
  to: Recipient[]
  cc: Recipient[]
  bcc: Recipient[]
  subject: string
  /** Editor content for a resumed draft; empty for a fresh message. */
  bodyHtml: string
  quotedHtml: string | null
  headers: ReplyHeaders | null
}

interface FormProps {
  composer: Composer
  initial: ComposeInitial
  variant: 'dock' | 'inline'
  onClose: () => void
}

export function ComposeForm({ composer, initial, variant, onClose }: FormProps) {
  const setDraftId = useComposeStore((s) => s.setDraftId)
  const setMinimized = useComposeStore((s) => s.setMinimized)
  const addPendingSend = useComposeStore((s) => s.addPendingSend)
  const qc = useQueryClient()

  const [fromAccountId, setFromAccountId] = useState(initial.fromAccountId)
  const [to, setTo] = useState<Recipient[]>(initial.to)
  const [cc, setCc] = useState<Recipient[]>(initial.cc)
  const [bcc, setBcc] = useState<Recipient[]>(initial.bcc)
  const [showCc, setShowCc] = useState(initial.cc.length > 0)
  const [showBcc, setShowBcc] = useState(initial.bcc.length > 0)
  const [subject, setSubject] = useState(initial.subject)
  const [bodyJson, setBodyJson] = useState('')
  const [bodyHtml, setBodyHtml] = useState(initial.bodyHtml)
  const [bodyText, setBodyText] = useState('')
  const [showQuoted, setShowQuoted] = useState(false)
  const [pendingFiles, setPendingFiles] = useState<File[]>([])
  const [dragging, setDragging] = useState(false)
  const [schedOpen, setSchedOpen] = useState(false)
  const [schedAt, setSchedAt] = useState('')
  const [busy, setBusy] = useState(false)
  const dirty = useRef(false)
  const fileInput = useRef<HTMLInputElement>(null)

  const { data: settings } = useSystemSettings()
  const { data: signatures } = useSignatures()
  const createDraft = useCreateDraft()
  const updateDraft = useUpdateDraft()
  const sendEmail = useSendEmail()
  const attachments = useDraftAttachments(composer.draftId)
  const removeAttachment = useRemoveDraftAttachment()

  const undoSeconds = Number(settings?.mail_undo_send_seconds ?? '10')
  const signature = defaultSignature(signatures ?? [], fromAccountId)

  const payload = () => ({
    from_account_id: fromAccountId,
    to_addresses: to,
    cc_addresses: cc,
    bcc_addresses: bcc,
    subject,
    body_json: bodyJson,
    body_html: initial.quotedHtml
      ? `${bodyHtml}<div class="quoted-content" style="margin-top: 16px;">${initial.quotedHtml}</div>`
      : bodyHtml,
    body_text: bodyText,
    source_type: composer.mode === 'reply' || composer.mode === 'reply_all' ? 'reply' : composer.mode === 'forward' ? 'forward' : 'manual',
    reply_to_communication_id: initial.headers?.reply_to_communication_id ?? null,
    forward_of_communication_id: initial.headers?.forward_of_communication_id ?? null,
    conversation_id: initial.headers?.conversation_id ?? null,
    signature_id: signature?.id ?? null,
  })

  /** Create or update the draft, upload any files picked before it existed, return its id. */
  const ensureDraft = async (): Promise<string> => {
    let id = composer.draftId
    if (id) await updateDraft.mutateAsync({ draftId: id, ...payload() })
    else {
      const d = await createDraft.mutateAsync(payload())
      id = d.id
      setDraftId(composer.id, id)
    }
    if (pendingFiles.length > 0) {
      await uploadDraftAttachments(id, pendingFiles)
      setPendingFiles([])
      qc.invalidateQueries({ queryKey: ['outbound-attachments', id] })
    }
    dirty.current = false
    return id
  }

  const canSave = !!fromAccountId && !!subject.trim() && to.length > 0

  const saveDraft = async (quiet = false) => {
    if (!canSave) { if (!quiet) toast.error('A draft needs a sending account, a recipient, and a subject'); return }
    try { await ensureDraft(); if (!quiet) toast.success('Draft saved') }
    catch (err) { if (!quiet) toast.error(`Could not save: ${err instanceof Error ? err.message : String(err)}`) }
  }

  // Autosave (MAIL-35): only a draft that already exists, and only when changed.
  const draftId = composer.draftId
  useEffect(() => {
    if (!draftId) return
    const timer = window.setInterval(() => { if (dirty.current) saveDraft(true) }, AUTO_SAVE_INTERVAL)
    return () => window.clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- saveDraft reads the latest state through closure each tick
  }, [draftId])

  const send = async (opts: SendOptions) => {
    if (!fromAccountId) { toast.error('Choose a sending account'); return }
    if (to.length === 0) { toast.error('Add at least one recipient'); return }
    if (!subject.trim()) { toast.error('Enter a subject'); return }
    setBusy(true)
    try {
      const id = await ensureDraft()
      const r = await sendEmail.mutateAsync({ draftId: id, ...opts })
      if (r.status === 'failed') { toast.error(`Send failed: ${r.failure_reason || 'unknown error'}`); return }
      if (r.status === 'queued' && r.scheduled_send_at) {
        addPendingSend({ draftId: id, subject, sendAt: Date.parse(r.scheduled_send_at), scheduled: !!opts.scheduled_send_at })
      } else {
        toast.success('Sent')
        qc.invalidateQueries({ queryKey: ['mail'] })
      }
      onClose()
    } catch (err) {
      toast.error(`Could not send: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setBusy(false)
    }
  }
  const sendDefault = () => send(undoSeconds > 0 ? { undo: true } : {})

  const addFiles = (files: FileList | File[]) => {
    const list = Array.from(files)
    if (list.length === 0) return
    dirty.current = true
    if (composer.draftId) {
      const id = composer.draftId
      uploadDraftAttachments(id, list)
        .then(() => qc.invalidateQueries({ queryKey: ['outbound-attachments', id] }))
        .catch((err) => toast.error(`Could not attach: ${err instanceof Error ? err.message : String(err)}`))
    } else {
      setPendingFiles((prev) => [...prev, ...list])
    }
  }
  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault(); setDragging(false)
    if (e.dataTransfer.files?.length) addFiles(e.dataTransfer.files)
  }

  const discard = () => {
    const hasContent = bodyText.trim() || subject.trim() || to.length > 0
    if (dirty.current && hasContent && !composer.draftId && !window.confirm('Discard this message?')) return
    onClose()
  }

  const onKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); if (!busy) sendDefault() }
    else if (e.key === 'Escape' && variant === 'dock') { e.preventDefault(); setMinimized(composer.id, true) }
  }

  const mark = () => { dirty.current = true }
  const pad = variant === 'inline' ? 'px-4' : 'px-4'

  return (
    <div
      className={`relative flex min-h-0 flex-1 flex-col ${dragging ? 'ring-2 ring-primary-400' : ''}`}
      onKeyDown={onKeyDown}
      onDragOver={(e) => { e.preventDefault(); if (!dragging) setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      data-testid="compose-form"
    >
      <div className={`space-y-1.5 border-b border-surface-200 ${pad} py-2`}>
        <div className="flex items-center gap-2">
          <label className="w-14 shrink-0 text-xs font-medium text-surface-500">From</label>
          <div className="flex-1"><SendingAccountSelector value={fromAccountId} onChange={(v) => { mark(); setFromAccountId(v) }} /></div>
        </div>
        <RecipientField label="To" recipients={to} onChange={(r) => { mark(); setTo(r) }} />
        {showCc && <RecipientField label="CC" recipients={cc} onChange={(r) => { mark(); setCc(r) }} />}
        {showBcc && <RecipientField label="BCC" recipients={bcc} onChange={(r) => { mark(); setBcc(r) }} />}
        {(!showCc || !showBcc) && (
          <div className="flex gap-2 pl-[60px]">
            {!showCc && <button type="button" onClick={() => setShowCc(true)} className="text-xs text-primary-600 hover:underline">CC</button>}
            {!showBcc && <button type="button" onClick={() => setShowBcc(true)} className="text-xs text-primary-600 hover:underline">BCC</button>}
          </div>
        )}
        <div className="flex items-center gap-2">
          <label className="w-14 shrink-0 text-xs font-medium text-surface-500">Subject</label>
          <input
            type="text"
            value={subject}
            onChange={(e) => { mark(); setSubject(e.target.value) }}
            placeholder="Subject"
            aria-label="Subject"
            className="flex-1 rounded border border-surface-200 bg-white px-2 py-1 text-sm text-surface-800 focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
          />
        </div>
      </div>

      <div className={`min-h-0 flex-1 overflow-y-auto ${pad} py-2`}>
        <RichTextEditor
          content={initial.bodyHtml || null}
          onChange={(j, h, t) => { mark(); setBodyJson(j); setBodyHtml(h); setBodyText(t) }}
          placeholder="Write your message…"
          autoFocus={variant === 'dock' || composer.mode !== 'new'}
          className={variant === 'inline' ? 'min-h-[140px]' : 'min-h-[200px]'}
        />
        {signature && (
          <div className="mt-2 rounded border border-dashed border-surface-200 px-2 py-1 text-xs text-surface-500" title="Added when the message is sent">
            <div className="mb-0.5 text-[10px] uppercase tracking-wide text-surface-400">Signature · {signature.name}</div>
            <div className="text-surface-600" dangerouslySetInnerHTML={{ __html: signature.body_html }} />
          </div>
        )}
        {initial.quotedHtml && (
          <div className="mt-2">
            <button type="button" onClick={() => setShowQuoted((v) => !v)} className="flex items-center gap-1 text-xs text-surface-400 hover:text-surface-600">
              {showQuoted ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
              {composer.mode === 'forward' ? 'Forwarded message' : 'Quoted text'}
            </button>
            {showQuoted && (
              <div className="mt-2 border-l-2 border-surface-300 pl-3 text-sm text-surface-500" dangerouslySetInnerHTML={{ __html: initial.quotedHtml }} />
            )}
          </div>
        )}
        {(pendingFiles.length > 0 || (attachments.data?.length ?? 0) > 0) && (
          <ul className="mt-2 flex flex-wrap gap-1 text-xs" aria-label="Attachments">
            {attachments.data?.map((a) => (
              <li key={a.id} className="inline-flex items-center gap-1 rounded border border-surface-200 px-1.5 py-0.5">
                <Paperclip size={11} /> <span className="max-w-[200px] truncate">{a.filename}</span>
                <span className="text-surface-400">{fmtBytes(a.size_bytes)}</span>
                <button type="button" aria-label={`Remove ${a.filename}`} className="text-surface-400 hover:text-red-600"
                  onClick={() => removeAttachment.mutate({ draftId: composer.draftId!, attachmentId: a.id })}>
                  <X size={11} />
                </button>
              </li>
            ))}
            {pendingFiles.map((f, i) => (
              <li key={`${f.name}-${i}`} className="inline-flex items-center gap-1 rounded border border-dashed border-surface-300 px-1.5 py-0.5">
                <Paperclip size={11} /> <span className="max-w-[200px] truncate">{f.name}</span>
                <span className="text-surface-400">{fmtBytes(f.size)}</span>
                <button type="button" aria-label={`Remove ${f.name}`} className="text-surface-400 hover:text-red-600"
                  onClick={() => setPendingFiles((prev) => prev.filter((_, j) => j !== i))}>
                  <X size={11} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className={`flex items-center justify-between border-t border-surface-200 ${pad} py-2`}>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={sendDefault}
            disabled={busy}
            title="Send (Ctrl+Enter)"
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
          >
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />} Send
          </button>
          <div className="relative">
            <button
              type="button"
              onClick={() => setSchedOpen((v) => !v)}
              disabled={busy}
              title="Schedule send"
              aria-label="Schedule send"
              className="inline-flex items-center rounded-lg border border-surface-200 px-2 py-1.5 text-surface-600 hover:bg-surface-50 disabled:opacity-50"
            >
              <CalendarClock size={14} />
            </button>
            {schedOpen && (
              <div className="absolute bottom-full left-0 z-10 mb-1 w-64 rounded-md border border-surface-200 bg-white p-2 shadow-lg">
                <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-surface-500">Send later</div>
                <ul className="mb-2 space-y-0.5">
                  {scheduleOptions(new Date()).map((o) => (
                    <li key={o.label}>
                      <button type="button" className="w-full rounded px-1.5 py-0.5 text-left text-xs hover:bg-surface-100"
                        onClick={() => { setSchedOpen(false); send({ scheduled_send_at: o.at.toISOString() }) }}>
                        {o.label} <span className="text-surface-400">{o.at.toLocaleString([], { weekday: 'short', hour: 'numeric', minute: '2-digit' })}</span>
                      </button>
                    </li>
                  ))}
                </ul>
                <div className="flex items-center gap-1">
                  <input type="datetime-local" value={schedAt} onChange={(e) => setSchedAt(e.target.value)} aria-label="Send at"
                    className="min-w-0 flex-1 rounded border border-surface-200 px-1 py-0.5 text-xs" />
                  <button type="button" disabled={!schedAt || Number.isNaN(Date.parse(schedAt))}
                    className="rounded bg-primary-600 px-2 py-0.5 text-xs text-white disabled:opacity-50"
                    onClick={() => { setSchedOpen(false); send({ scheduled_send_at: new Date(schedAt).toISOString() }) }}>
                    Schedule
                  </button>
                </div>
              </div>
            )}
          </div>
          <button type="button" onClick={() => fileInput.current?.click()} disabled={busy} title="Attach files" aria-label="Attach files"
            className="inline-flex items-center rounded-lg border border-surface-200 px-2 py-1.5 text-surface-600 hover:bg-surface-50 disabled:opacity-50">
            <Paperclip size={14} />
          </button>
          <input ref={fileInput} type="file" multiple className="hidden" aria-label="Attachment files"
            onChange={(e) => { if (e.target.files) addFiles(e.target.files); e.target.value = '' }} />
          <button type="button" onClick={() => saveDraft()} disabled={busy || !canSave} title="Save draft"
            className="inline-flex items-center gap-1 rounded-lg border border-surface-200 px-2 py-1.5 text-xs text-surface-600 hover:bg-surface-50 disabled:opacity-50">
            <Save size={13} /> Save
          </button>
        </div>
        <button type="button" onClick={discard} className="text-xs text-surface-400 hover:text-surface-600">Discard</button>
      </div>
    </div>
  )
}

/** Decide what the form starts from, then mount it. */
export function ComposeFormLoader({ composer, variant, onClose }: { composer: Composer; variant: 'dock' | 'inline'; onClose: () => void }) {
  const commId = composer.mode !== 'new' && !composer.resume ? composer.context?.communicationId : undefined
  const ctx = useComposeContext(commId, composer.mode)
  const { data: accounts } = useAccounts()

  if (commId && !ctx.data) {
    return <div className="p-4 text-sm text-surface-500">{ctx.error ? 'Could not load the message to reply to.' : 'Loading…'}</div>
  }
  const resume: OutboundDraft | null = composer.resume
  const active = accounts?.filter((a) => a.is_active) ?? []
  const initial: ComposeInitial = resume
    ? { fromAccountId: resume.from_account_id, to: resume.to_addresses, cc: resume.cc_addresses ?? [], bcc: resume.bcc_addresses ?? [],
        subject: resume.subject, bodyHtml: resume.body_html, quotedHtml: null,
        headers: { conversation_id: resume.conversation_id, reply_to_communication_id: resume.reply_to_communication_id, forward_of_communication_id: resume.forward_of_communication_id } }
    : ctx.data
      ? { fromAccountId: ctx.data.default_account_id || (active.length === 1 ? active[0].id : ''),
          to: ctx.data.to_addresses ?? [], cc: ctx.data.cc_addresses ?? [], bcc: [], subject: ctx.data.subject ?? '', bodyHtml: '',
          quotedHtml: ctx.data.quoted_html || null,
          headers: { conversation_id: ctx.data.conversation_id, reply_to_communication_id: ctx.data.reply_to_communication_id ?? null,
                     forward_of_communication_id: ctx.data.forward_of_communication_id ?? null } }
      : { fromAccountId: active.length === 1 ? active[0].id : '', to: [], cc: [], bcc: [], subject: '', bodyHtml: '', quotedHtml: null, headers: null }
  return <ComposeForm key={composer.id} composer={composer} initial={initial} variant={variant} onClose={onClose} />
}
