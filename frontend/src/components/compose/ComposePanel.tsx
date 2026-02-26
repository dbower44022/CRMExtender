import { useState, useEffect, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { X, Send, Save, ChevronDown, ChevronRight, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { useComposeStore } from '../../stores/compose.ts'
import { useAccounts } from '../../api/settings.ts'
import {
  useCreateDraft,
  useSendEmail,
  useUpdateDraft,
  useComposeContext,
  type Recipient,
} from '../../api/outbound.ts'
import { RecipientField } from './RecipientField.tsx'
import { SendingAccountSelector } from './SendingAccountSelector.tsx'
import { RichTextEditor } from '../editor/RichTextEditor.tsx'

const AUTO_SAVE_INTERVAL = 30_000 // 30 seconds

export function ComposePanel() {
  const { isOpen, mode, context, draftId, closeCompose, setDraftId } = useComposeStore()

  const [fromAccountId, setFromAccountId] = useState('')
  const [toRecipients, setToRecipients] = useState<Recipient[]>([])
  const [ccRecipients, setCcRecipients] = useState<Recipient[]>([])
  const [bccRecipients, setBccRecipients] = useState<Recipient[]>([])
  const [showCc, setShowCc] = useState(false)
  const [showBcc, setShowBcc] = useState(false)
  const [subject, setSubject] = useState('')
  const [bodyJson, setBodyJson] = useState('')
  const [bodyHtml, setBodyHtml] = useState('')
  const [bodyText, setBodyText] = useState('')
  const [quotedHtml, setQuotedHtml] = useState<string | null>(null)
  const [showQuoted, setShowQuoted] = useState(false)
  const [replyHeaders, setReplyHeaders] = useState<{
    in_reply_to: string | null
    references: string | null
    thread_id: string | null
    conversation_id: string | null
    reply_to_communication_id: string | null
    forward_of_communication_id: string | null
  } | null>(null)

  const isDirty = useRef(false)
  const lastSavedAt = useRef<number>(0)

  const { data: accounts } = useAccounts()
  const createDraft = useCreateDraft()
  const updateDraft = useUpdateDraft()
  const sendEmail = useSendEmail()

  // Fetch compose context for reply/forward
  const commId = (mode === 'reply' || mode === 'reply_all' || mode === 'forward')
    ? context?.communicationId
    : undefined
  const { data: composeCtx } = useComposeContext(commId, mode)

  // Pre-fill from compose context
  useEffect(() => {
    if (!composeCtx) return
    setToRecipients(composeCtx.to_addresses ?? [])
    setCcRecipients(composeCtx.cc_addresses ?? [])
    if (composeCtx.cc_addresses?.length) setShowCc(true)
    setSubject(composeCtx.subject ?? '')
    if (composeCtx.quoted_html) setQuotedHtml(composeCtx.quoted_html)
    if (composeCtx.default_account_id) setFromAccountId(composeCtx.default_account_id)
    setReplyHeaders({
      in_reply_to: composeCtx.in_reply_to,
      references: composeCtx.references,
      thread_id: composeCtx.thread_id,
      conversation_id: composeCtx.conversation_id,
      reply_to_communication_id: composeCtx.reply_to_communication_id ?? null,
      forward_of_communication_id: composeCtx.forward_of_communication_id ?? null,
    })
  }, [composeCtx])

  // Set default account for new compose
  useEffect(() => {
    if (mode === 'new' && !fromAccountId && accounts) {
      const active = accounts.filter((a) => a.is_active)
      if (active.length === 1) setFromAccountId(active[0].id)
    }
  }, [mode, fromAccountId, accounts])

  // Auto-save timer
  useEffect(() => {
    if (!isOpen) return
    const timer = setInterval(() => {
      if (isDirty.current && draftId) {
        saveDraft()
      }
    }, AUTO_SAVE_INTERVAL)
    return () => clearInterval(timer)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, draftId])

  // Mark dirty on any field change
  useEffect(() => {
    isDirty.current = true
  }, [toRecipients, ccRecipients, bccRecipients, subject, bodyJson, fromAccountId])

  const getSourceType = useCallback(() => {
    if (mode === 'reply' || mode === 'reply_all') return 'reply'
    if (mode === 'forward') return 'forward'
    return 'manual'
  }, [mode])

  const buildDraftPayload = useCallback(() => {
    // Combine compose body + quoted content for the final HTML
    let finalHtml = bodyHtml
    if (quotedHtml) {
      finalHtml += `<div class="quoted-content" style="margin-top: 16px;">${quotedHtml}</div>`
    }

    return {
      from_account_id: fromAccountId,
      to_addresses: toRecipients,
      cc_addresses: ccRecipients,
      bcc_addresses: bccRecipients,
      subject,
      body_json: bodyJson,
      body_html: finalHtml,
      body_text: bodyText,
      source_type: getSourceType(),
      reply_to_communication_id: replyHeaders?.reply_to_communication_id ?? null,
      forward_of_communication_id: replyHeaders?.forward_of_communication_id ?? null,
      conversation_id: replyHeaders?.conversation_id ?? null,
    }
  }, [fromAccountId, toRecipients, ccRecipients, bccRecipients, subject, bodyJson, bodyHtml, bodyText, quotedHtml, replyHeaders, getSourceType])

  const saveDraft = useCallback(async () => {
    if (!fromAccountId || !subject.trim()) return

    try {
      if (draftId) {
        await updateDraft.mutateAsync({ draftId, ...buildDraftPayload() })
      } else {
        const result = await createDraft.mutateAsync(buildDraftPayload())
        setDraftId(result.id)
      }
      isDirty.current = false
      lastSavedAt.current = Date.now()
    } catch {
      // Silent failure for auto-save
    }
  }, [draftId, fromAccountId, subject, buildDraftPayload, createDraft, updateDraft, setDraftId])

  const handleSend = async () => {
    if (!fromAccountId) {
      toast.error('Please select a sending account')
      return
    }
    if (toRecipients.length === 0) {
      toast.error('Please add at least one recipient')
      return
    }
    if (!subject.trim()) {
      toast.error('Please enter a subject')
      return
    }

    try {
      // Create draft first if not yet saved
      let id = draftId
      if (!id) {
        const draft = await createDraft.mutateAsync(buildDraftPayload())
        id = draft.id
        setDraftId(id)
      } else {
        // Save latest changes
        await updateDraft.mutateAsync({ draftId: id, ...buildDraftPayload() })
      }

      // Send
      const result = await sendEmail.mutateAsync(id)
      if (result.status === 'failed') {
        toast.error(`Send failed: ${result.failure_reason || 'Unknown error'}`)
      } else {
        toast.success('Email sent successfully')
        closeCompose()
      }
    } catch (err) {
      toast.error(`Failed to send: ${err instanceof Error ? err.message : 'Unknown error'}`)
    }
  }

  const handleDiscard = () => {
    if (isDirty.current && (bodyText.trim() || subject.trim() || toRecipients.length > 0)) {
      if (!confirm('Discard this draft?')) return
    }
    closeCompose()
  }

  const handleEditorChange = (json: string, html: string, text: string) => {
    setBodyJson(json)
    setBodyHtml(html)
    setBodyText(text)
  }

  // Escape key to close
  useEffect(() => {
    if (!isOpen) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleDiscard()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen])

  if (!isOpen) return null

  const isSending = sendEmail.isPending || createDraft.isPending

  const modeLabel =
    mode === 'reply' ? 'Reply' :
    mode === 'reply_all' ? 'Reply All' :
    mode === 'forward' ? 'Forward' :
    'New Email'

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => {
        if (e.target === e.currentTarget) handleDiscard()
      }}
    >
      <div
        className="flex max-h-[90vh] w-full max-w-[760px] flex-col rounded-xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-surface-200 px-5 py-3">
          <h2 className="text-sm font-semibold text-surface-800">{modeLabel}</h2>
          <button
            onClick={handleDiscard}
            className="rounded p-1 text-surface-400 hover:bg-surface-100 hover:text-surface-600"
          >
            <X size={16} />
          </button>
        </div>

        {/* Form fields */}
        <div className="space-y-2 border-b border-surface-200 px-5 py-3">
          {/* From */}
          <div className="flex items-center gap-2">
            <label className="shrink-0 text-sm font-medium text-surface-500">From:</label>
            <div className="flex-1">
              <SendingAccountSelector value={fromAccountId} onChange={setFromAccountId} />
            </div>
          </div>

          {/* To */}
          <RecipientField
            label="To"
            recipients={toRecipients}
            onChange={setToRecipients}
          />

          {/* CC / BCC toggles */}
          {!showCc && !showBcc && (
            <div className="flex gap-2 pl-[60px]">
              <button
                type="button"
                onClick={() => setShowCc(true)}
                className="text-xs text-primary-600 hover:underline"
              >
                CC
              </button>
              <button
                type="button"
                onClick={() => setShowBcc(true)}
                className="text-xs text-primary-600 hover:underline"
              >
                BCC
              </button>
            </div>
          )}

          {showCc && (
            <RecipientField
              label="CC"
              recipients={ccRecipients}
              onChange={setCcRecipients}
            />
          )}

          {showCc && !showBcc && (
            <div className="pl-[60px]">
              <button
                type="button"
                onClick={() => setShowBcc(true)}
                className="text-xs text-primary-600 hover:underline"
              >
                BCC
              </button>
            </div>
          )}

          {showBcc && (
            <RecipientField
              label="BCC"
              recipients={bccRecipients}
              onChange={setBccRecipients}
            />
          )}

          {/* Subject */}
          <div className="flex items-center gap-2">
            <label className="shrink-0 text-sm font-medium text-surface-500">Subject:</label>
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Email subject"
              className="flex-1 rounded border border-surface-200 bg-white px-3 py-1.5 text-sm text-surface-800 focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
            />
          </div>
        </div>

        {/* Editor */}
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-3">
          <RichTextEditor
            onChange={handleEditorChange}
            placeholder="Write your message..."
            autoFocus
            className="min-h-[200px]"
          />

          {/* Quoted content (reply/forward) */}
          {quotedHtml && (
            <div className="mt-3">
              <button
                type="button"
                onClick={() => setShowQuoted(!showQuoted)}
                className="flex items-center gap-1 text-xs text-surface-400 hover:text-surface-600"
              >
                {showQuoted ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                {mode === 'forward' ? 'Forwarded message' : 'Quoted text'}
              </button>
              {showQuoted && (
                <div
                  className="mt-2 border-l-2 border-surface-300 pl-3 text-sm text-surface-500"
                  dangerouslySetInnerHTML={{ __html: quotedHtml }}
                />
              )}
            </div>
          )}
        </div>

        {/* Footer / Actions */}
        <div className="flex items-center justify-between border-t border-surface-200 px-5 py-3">
          <div className="flex items-center gap-2">
            <button
              onClick={handleSend}
              disabled={isSending}
              className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
            >
              {isSending ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Send size={14} />
              )}
              Send
            </button>
            <button
              onClick={() => saveDraft()}
              disabled={isSending}
              className="inline-flex items-center gap-2 rounded-lg border border-surface-200 px-3 py-2 text-sm text-surface-600 hover:bg-surface-50 disabled:opacity-50"
            >
              <Save size={14} />
              Save Draft
            </button>
          </div>
          <button
            onClick={handleDiscard}
            className="text-sm text-surface-400 hover:text-surface-600"
          >
            Discard
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
