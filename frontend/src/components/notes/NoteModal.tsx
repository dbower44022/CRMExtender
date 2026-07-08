import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { History, Loader2, Paperclip, Pin, Trash2, X } from 'lucide-react'
import { toast } from 'sonner'
import { RichTextEditor } from '../editor/RichTextEditor.tsx'
import { sanitizeHtml } from '../../lib/sanitizeHtml.ts'
import { formatTimestamp } from '../../lib/formatTimestamp.ts'
import {
  notesApi,
  useInvalidateNotes,
  type Note,
  type NoteRevision,
} from '../../api/notes.ts'

interface NoteModalProps {
  entityType: string
  entityId: string
  /** null = create a new note */
  note: Note | null
  onClose: () => void
}

export function NoteModal({ entityType, entityId, note, onClose }: NoteModalProps) {
  const invalidate = useInvalidateNotes(entityType, entityId)
  const isNew = note === null

  const [title, setTitle] = useState(note?.title ?? '')
  const [contentJson, setContentJson] = useState(note?.content_json ?? '')
  const [contentHtml, setContentHtml] = useState(note?.content_html ?? '')
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const [pinned, setPinned] = useState(!!note?.is_pinned)
  const attachmentIds = useRef<string[]>([])
  const fileInput = useRef<HTMLInputElement>(null)

  const [showRevisions, setShowRevisions] = useState(false)
  const [revisions, setRevisions] = useState<NoteRevision[] | null>(null)
  const [previewRevision, setPreviewRevision] = useState<NoteRevision | null>(null)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  const handleSave = async () => {
    setSaving(true)
    try {
      const body = {
        title: title.trim() || undefined,
        content_json: contentJson || undefined,
        content_html: contentHtml || undefined,
        attachment_ids: attachmentIds.current.length
          ? attachmentIds.current
          : undefined,
      }
      if (isNew) {
        await notesApi.create({
          entity_type: entityType, entity_id: entityId, ...body,
        })
        toast.success('Note created')
      } else {
        await notesApi.update(note.id, body)
        toast.success('Note saved')
      }
      invalidate()
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!note) return
    if (!confirmingDelete) {
      setConfirmingDelete(true)
      return
    }
    try {
      await notesApi.remove(note.id)
      toast.success('Note deleted')
      invalidate()
      onClose()
    } catch {
      toast.error('Delete failed')
    }
  }

  const handlePin = async () => {
    if (!note) return
    try {
      const res = await notesApi.pin(note.id, entityType, entityId)
      setPinned(res.is_pinned)
      invalidate()
    } catch {
      toast.error('Pin failed')
    }
  }

  const handleAttach = async (file: File) => {
    try {
      const up = await notesApi.upload(file)
      attachmentIds.current.push(up.id)
      setDirty(true)
      const isImage = file.type.startsWith('image/')
      const fragment = isImage
        ? `<img src="${up.url}" alt="${up.original_name}">`
        : `<a href="${up.url}">${up.original_name}</a>`
      setContentHtml((prev) => (prev || '') + fragment)
      toast.success(
        `${up.original_name} attached${isImage ? '' : ' (link added below)'}`,
      )
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Upload failed')
    }
  }

  const loadRevisions = async () => {
    if (!note) return
    setShowRevisions(true)
    try {
      const res = await notesApi.revisions(note.id)
      setRevisions(res.revisions)
    } catch {
      toast.error('Could not load revisions')
    }
  }

  const openRevision = async (rev: NoteRevision) => {
    if (!note) return
    try {
      setPreviewRevision(await notesApi.revision(note.id, rev.id))
    } catch {
      toast.error('Could not load revision')
    }
  }

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="relative mx-4 flex max-h-[85vh] w-full max-w-2xl flex-col rounded-lg bg-white shadow-xl">
        {/* Header */}
        <div className="flex items-center gap-2 border-b border-surface-200 px-5 py-3">
          <input
            value={title}
            onChange={(e) => { setTitle(e.target.value); setDirty(true) }}
            placeholder="Note title…"
            className="min-w-0 flex-1 bg-transparent text-base font-semibold text-surface-900 placeholder:text-surface-300 focus:outline-none"
          />
          {!isNew && (
            <>
              <button
                onClick={handlePin}
                title={pinned ? 'Unpin' : 'Pin to this record'}
                className={`rounded p-1.5 ${pinned ? 'text-amber-500' : 'text-surface-400 hover:bg-surface-100'}`}
              >
                <Pin size={15} fill={pinned ? 'currentColor' : 'none'} />
              </button>
              <button
                onClick={loadRevisions}
                title="Revision history"
                className="rounded p-1.5 text-surface-400 hover:bg-surface-100 hover:text-surface-600"
              >
                <History size={15} />
              </button>
              <button
                onClick={handleDelete}
                onBlur={() => setConfirmingDelete(false)}
                title="Delete note"
                className={confirmingDelete
                  ? 'rounded bg-red-600 px-2 py-1 text-xs font-medium text-white'
                  : 'rounded p-1.5 text-surface-400 hover:bg-red-50 hover:text-red-600'}
              >
                {confirmingDelete ? 'Confirm?' : <Trash2 size={15} />}
              </button>
            </>
          )}
          <button
            onClick={onClose}
            className="rounded p-1.5 text-surface-400 hover:bg-surface-100 hover:text-surface-600"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {showRevisions && (
            <RevisionsPanel
              revisions={revisions}
              onOpen={openRevision}
              onClose={() => { setShowRevisions(false); setPreviewRevision(null) }}
            />
          )}
          {previewRevision ? (
            <div>
              <div className="mb-2 flex items-center justify-between text-xs text-surface-500">
                <span>
                  Viewing revision {previewRevision.revision_number} ·{' '}
                  {formatTimestamp(previewRevision.created_at)}
                </span>
                <button
                  onClick={() => setPreviewRevision(null)}
                  className="font-medium text-primary-600 hover:underline"
                >
                  Back to current
                </button>
              </div>
              <div
                className="prose prose-sm max-w-none rounded-md border border-surface-200 bg-surface-50 p-3"
                dangerouslySetInnerHTML={{
                  __html: sanitizeHtml(previewRevision.content_html || ''),
                }}
              />
            </div>
          ) : (
            <RichTextEditor
              content={contentHtml || null}
              placeholder="Write a note… use @ to mention someone"
              mentions
              autoFocus={isNew}
              onChange={(json, html) => {
                setContentJson(json)
                setContentHtml(html)
                setDirty(true)
              }}
            />
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center gap-2 border-t border-surface-200 px-5 py-3">
          <input
            ref={fileInput}
            type="file"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) handleAttach(f)
              e.target.value = ''
            }}
          />
          <button
            onClick={() => fileInput.current?.click()}
            className="flex items-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-medium text-surface-500 hover:bg-surface-100"
          >
            <Paperclip size={13} /> Attach file
          </button>
          <div className="ml-auto flex items-center gap-2">
            {note?.author_name && (
              <span className="text-xs text-surface-400">
                {note.author_name} · {formatTimestamp(note.updated_at)}
              </span>
            )}
            <button
              onClick={handleSave}
              disabled={saving || (!dirty && !isNew)}
              className="flex items-center gap-1.5 rounded-md bg-primary-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
            >
              {saving && <Loader2 size={13} className="animate-spin" />}
              {isNew ? 'Create note' : 'Save'}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}

function RevisionsPanel({ revisions, onOpen, onClose }: {
  revisions: NoteRevision[] | null
  onOpen: (rev: NoteRevision) => void
  onClose: () => void
}) {
  return (
    <div className="mb-4 rounded-md border border-surface-200 bg-surface-50 p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase text-surface-500">
          Revision history
        </span>
        <button onClick={onClose} className="text-surface-400 hover:text-surface-600">
          <X size={13} />
        </button>
      </div>
      {revisions === null ? (
        <div className="text-xs text-surface-400">Loading…</div>
      ) : (
        <ul className="space-y-1">
          {revisions.map((rev) => (
            <li key={rev.id}>
              <button
                onClick={() => onOpen(rev)}
                className="w-full rounded px-2 py-1 text-left text-xs text-surface-600 hover:bg-white"
              >
                #{rev.revision_number} · {formatTimestamp(rev.created_at)}
                {rev.revised_by_name && ` · ${rev.revised_by_name}`}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
