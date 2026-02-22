import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { X, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { useCreateContact } from '../../api/contacts.ts'

interface AddContactModalProps {
  onClose: () => void
}

export function AddContactModal({ onClose }: AddContactModalProps) {
  const create = useCreateContact()

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [source, setSource] = useState('manual')
  const [error, setError] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!name.trim()) {
      setError('Name is required')
      return
    }

    create.mutate(
      {
        name: name.trim(),
        email: email.trim() || undefined,
        source: source.trim() || undefined,
      },
      {
        onSuccess: (result) => {
          toast.success(`Contact "${result.name}" created`)
          onClose()
        },
        onError: (err) => {
          setError(err.message || 'Failed to create contact')
        },
      },
    )
  }

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="relative mx-4 w-full max-w-md rounded-lg bg-white shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-surface-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-surface-900">Add Contact</h2>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-surface-400 hover:bg-surface-100 hover:text-surface-600"
          >
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} className="px-6 py-4">
          {error && (
            <div className="mb-4 rounded-md bg-red-50 px-4 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-surface-700">
                Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Full name"
                autoFocus
                className="h-9 w-full rounded-md border border-surface-200 bg-surface-0 px-3 text-sm text-surface-700 outline-none transition-colors placeholder:text-surface-400 focus:border-primary-300 focus:ring-1 focus:ring-primary-200"
              />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-surface-700">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="email@example.com"
                className="h-9 w-full rounded-md border border-surface-200 bg-surface-0 px-3 text-sm text-surface-700 outline-none transition-colors placeholder:text-surface-400 focus:border-primary-300 focus:ring-1 focus:ring-primary-200"
              />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-surface-700">
                Source
              </label>
              <input
                type="text"
                value={source}
                onChange={(e) => setSource(e.target.value)}
                placeholder="manual"
                className="h-9 w-full rounded-md border border-surface-200 bg-surface-0 px-3 text-sm text-surface-700 outline-none transition-colors placeholder:text-surface-400 focus:border-primary-300 focus:ring-1 focus:ring-primary-200"
              />
            </div>
          </div>

          {/* Footer */}
          <div className="mt-6 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-surface-200 bg-white px-4 py-2 text-sm font-medium text-surface-600 hover:bg-surface-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={create.isPending}
              className="flex items-center gap-2 rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {create.isPending && <Loader2 size={14} className="animate-spin" />}
              Create Contact
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body,
  )
}
