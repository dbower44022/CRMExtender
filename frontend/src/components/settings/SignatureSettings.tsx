import { useState } from 'react'
import { toast } from 'sonner'
import { Plus, Pencil, Trash2, Star } from 'lucide-react'
import {
  useSignatures,
  useCreateSignature,
  useUpdateSignature,
  useDeleteSignature,
  type Signature,
} from '../../api/outbound.ts'
import { useAccounts } from '../../api/settings.ts'
import { RichTextEditor } from '../editor/RichTextEditor.tsx'

export function SignatureSettings() {
  const { data: signatures, isLoading } = useSignatures()
  const { data: accounts } = useAccounts()
  const createSignature = useCreateSignature()
  const updateSignature = useUpdateSignature()
  const deleteSignature = useDeleteSignature()

  const [editingId, setEditingId] = useState<string | null>(null)
  const [isCreating, setIsCreating] = useState(false)

  // Form state
  const [formName, setFormName] = useState('')
  const [formBodyJson, setFormBodyJson] = useState('')
  const [formBodyHtml, setFormBodyHtml] = useState('')
  const [formAccountId, setFormAccountId] = useState<string>('')
  const [formIsDefault, setFormIsDefault] = useState(false)

  const activeAccounts = accounts?.filter((a) => a.is_active) ?? []

  const startCreate = () => {
    setEditingId(null)
    setIsCreating(true)
    setFormName('')
    setFormBodyJson('')
    setFormBodyHtml('')
    setFormAccountId('')
    setFormIsDefault(false)
  }

  const startEdit = (sig: Signature) => {
    setIsCreating(false)
    setEditingId(sig.id)
    setFormName(sig.name)
    setFormBodyJson(sig.body_json)
    setFormBodyHtml(sig.body_html)
    setFormAccountId(sig.provider_account_id ?? '')
    setFormIsDefault(!!sig.is_default)
  }

  const cancelEdit = () => {
    setEditingId(null)
    setIsCreating(false)
  }

  const handleEditorChange = (_json: string, html: string, _text: string) => {
    setFormBodyJson(_json)
    setFormBodyHtml(html)
  }

  const handleSave = () => {
    if (!formName.trim()) {
      toast.error('Name is required')
      return
    }
    if (!formBodyHtml.trim() || formBodyHtml === '<p></p>') {
      toast.error('Signature content is required')
      return
    }

    if (isCreating) {
      createSignature.mutate(
        {
          name: formName.trim(),
          body_json: formBodyJson,
          body_html: formBodyHtml,
          provider_account_id: formAccountId || null,
          is_default: formIsDefault,
        },
        {
          onSuccess: () => {
            toast.success('Signature created')
            cancelEdit()
          },
          onError: (err) => toast.error(err.message),
        },
      )
    } else if (editingId) {
      updateSignature.mutate(
        {
          signatureId: editingId,
          name: formName.trim(),
          body_json: formBodyJson,
          body_html: formBodyHtml,
          provider_account_id: formAccountId || null,
          is_default: formIsDefault,
        },
        {
          onSuccess: () => {
            toast.success('Signature updated')
            cancelEdit()
          },
          onError: (err) => toast.error(err.message),
        },
      )
    }
  }

  const handleDelete = (sig: Signature) => {
    if (!confirm(`Delete signature "${sig.name}"?`)) return
    deleteSignature.mutate(sig.id, {
      onSuccess: () => toast.success('Signature deleted'),
      onError: (err) => toast.error(err.message),
    })
  }

  if (isLoading) {
    return <div className="text-sm text-surface-500">Loading...</div>
  }

  return (
    <div className="w-full max-w-2xl">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-surface-800">Email Signatures</h1>
        {!isCreating && !editingId && (
          <button
            onClick={startCreate}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-700"
          >
            <Plus size={14} />
            New Signature
          </button>
        )}
      </div>

      {/* Editor form */}
      {(isCreating || editingId) && (
        <div className="mb-6 rounded-lg border border-surface-200 bg-surface-50 p-4">
          <h2 className="mb-3 text-sm font-semibold text-surface-700">
            {isCreating ? 'Create Signature' : 'Edit Signature'}
          </h2>
          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-surface-600">Name</label>
              <input
                type="text"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="e.g. Work, Personal"
                className="w-full rounded border border-surface-200 bg-white px-3 py-1.5 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-surface-600">Content</label>
              <RichTextEditor
                content={editingId ? formBodyJson : undefined}
                onChange={handleEditorChange}
                placeholder="Type your signature..."
                className="min-h-[120px]"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-surface-600">
                Account (optional)
              </label>
              <select
                value={formAccountId}
                onChange={(e) => setFormAccountId(e.target.value)}
                className="w-full rounded border border-surface-200 bg-white px-3 py-1.5 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
              >
                <option value="">All accounts</option>
                {activeAccounts.map((acc) => (
                  <option key={acc.id} value={acc.id}>
                    {acc.email_address}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-xs text-surface-400">
                Assign to a specific account, or leave blank to use for all.
              </p>
            </div>

            <label className="flex items-center gap-2 text-sm text-surface-600">
              <input
                type="checkbox"
                checked={formIsDefault}
                onChange={(e) => setFormIsDefault(e.target.checked)}
                className="rounded border-surface-300"
              />
              Set as default signature
            </label>

            <div className="flex items-center gap-2 pt-1">
              <button
                onClick={handleSave}
                disabled={createSignature.isPending || updateSignature.isPending}
                className="rounded-md bg-primary-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
              >
                {isCreating ? 'Create' : 'Save'}
              </button>
              <button
                onClick={cancelEdit}
                className="rounded-md px-4 py-1.5 text-sm text-surface-600 hover:bg-surface-100"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Signature list */}
      {(!signatures || signatures.length === 0) && !isCreating && (
        <p className="text-sm text-surface-500">
          No signatures yet. Create one to include in your outgoing emails.
        </p>
      )}

      {signatures && signatures.length > 0 && (
        <div className="space-y-3">
          {signatures.map((sig) => (
            <div
              key={sig.id}
              className="rounded-lg border border-surface-200 bg-white p-4"
            >
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-medium text-surface-800">{sig.name}</h3>
                  {sig.is_default === 1 && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-700">
                      <Star size={10} />
                      Default
                    </span>
                  )}
                  {sig.provider_account_id && (
                    <span className="text-xs text-surface-400">
                      ({activeAccounts.find((a) => a.id === sig.provider_account_id)?.email_address ?? 'Account'})
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => startEdit(sig)}
                    className="rounded p-1.5 text-surface-400 hover:bg-surface-100 hover:text-surface-600"
                    title="Edit"
                  >
                    <Pencil size={13} />
                  </button>
                  <button
                    onClick={() => handleDelete(sig)}
                    className="rounded p-1.5 text-surface-400 hover:bg-red-50 hover:text-red-500"
                    title="Delete"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
              <div
                className="text-sm text-surface-600"
                dangerouslySetInnerHTML={{ __html: sig.body_html }}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
