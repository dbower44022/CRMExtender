import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { X, Loader2, AlertTriangle } from 'lucide-react'
import { toast } from 'sonner'
import { useMergePreview, useMergeContacts } from '../../api/contacts.ts'
import { useNavigationStore } from '../../stores/navigation.ts'
import type { MergePreviewContact } from '../../types/api.ts'

interface MergeContactsModalProps {
  contactIds: string[]
  onClose: () => void
}

export function MergeContactsModal({ contactIds, onClose }: MergeContactsModalProps) {
  const deselectAllRows = useNavigationStore((s) => s.deselectAllRows)
  const preview = useMergePreview()
  const merge = useMergeContacts()

  const [survivingId, setSurvivingId] = useState<string>('')
  const [chosenName, setChosenName] = useState<string>('')
  const [chosenSource, setChosenSource] = useState<string>('')

  useEffect(() => {
    preview.mutate(contactIds)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Set defaults when preview loads
  useEffect(() => {
    if (preview.data) {
      const contacts = preview.data.contacts
      if (contacts.length > 0 && !survivingId) {
        setSurvivingId(contacts[0].id)
      }
      if (preview.data.conflicts.name.length > 0 && !chosenName) {
        setChosenName(preview.data.conflicts.name[0])
      }
      if (preview.data.conflicts.source.length > 0 && !chosenSource) {
        setChosenSource(preview.data.conflicts.source[0])
      }
    }
  }, [preview.data]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleConfirm = () => {
    const absorbedIds = contactIds.filter((id) => id !== survivingId)
    merge.mutate(
      {
        surviving_id: survivingId,
        absorbed_ids: absorbedIds,
        chosen_name: chosenName || undefined,
        chosen_source: chosenSource || undefined,
      },
      {
        onSuccess: (result) => {
          const count = result.absorbed_ids.length
          toast.success(
            `Merged ${count} contact${count > 1 ? 's' : ''} successfully. ` +
            `${result.identifiers_transferred} identifiers, ` +
            `${result.conversations_reassigned} conversations transferred.`
          )
          deselectAllRows()
          onClose()
        },
        onError: (error) => {
          toast.error(`Merge failed: ${error.message}`)
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
      <div className="relative mx-4 flex max-h-[80vh] w-full max-w-2xl flex-col rounded-lg bg-white shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-surface-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-surface-900">
            Merge {contactIds.length} Contacts
          </h2>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-surface-400 hover:bg-surface-100 hover:text-surface-600"
          >
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {preview.isPending && (
            <div className="flex items-center justify-center py-12">
              <Loader2 size={24} className="animate-spin text-primary-500" />
              <span className="ml-2 text-sm text-surface-500">Loading preview...</span>
            </div>
          )}

          {preview.isError && (
            <div className="flex items-center gap-2 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
              <AlertTriangle size={16} />
              {preview.error.message}
            </div>
          )}

          {preview.data && (
            <>
              {/* Surviving contact selection */}
              <div className="mb-5">
                <h3 className="mb-2 text-sm font-medium text-surface-700">
                  Select surviving contact
                </h3>
                <p className="mb-3 text-xs text-surface-500">
                  All data from other contacts will be transferred to the surviving contact.
                  The other contacts will be deleted.
                </p>
                <div className="space-y-2">
                  {preview.data.contacts.map((contact: MergePreviewContact) => (
                    <label
                      key={contact.id}
                      className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors ${
                        survivingId === contact.id
                          ? 'border-primary-300 bg-primary-50'
                          : 'border-surface-200 hover:bg-surface-50'
                      }`}
                    >
                      <input
                        type="radio"
                        name="surviving"
                        checked={survivingId === contact.id}
                        onChange={() => setSurvivingId(contact.id)}
                        className="mt-0.5"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-surface-900">
                            {contact.name}
                          </span>
                          {contact.source && (
                            <span className="rounded bg-surface-100 px-1.5 py-0.5 text-[10px] text-surface-500">
                              {contact.source}
                            </span>
                          )}
                        </div>
                        <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-surface-500">
                          <span>{contact.identifier_count} identifiers</span>
                          <span>{contact.affiliation_count} affiliations</span>
                          <span>{contact.conversation_count} conversations</span>
                          <span>{contact.relationship_count} relationships</span>
                          <span>{contact.event_count} events</span>
                        </div>
                        {contact.identifiers.length > 0 && (
                          <div className="mt-1 text-xs text-surface-400">
                            {contact.identifiers
                              .filter((i) => i.type === 'email')
                              .map((i) => i.value)
                              .join(', ')}
                          </div>
                        )}
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              {/* Conflict resolution: name */}
              {preview.data.conflicts.name.length > 1 && (
                <div className="mb-5">
                  <h3 className="mb-2 text-sm font-medium text-surface-700">
                    Choose name
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {preview.data.conflicts.name.map((name: string) => (
                      <label
                        key={name}
                        className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-1.5 text-sm transition-colors ${
                          chosenName === name
                            ? 'border-primary-300 bg-primary-50 text-primary-700'
                            : 'border-surface-200 text-surface-600 hover:bg-surface-50'
                        }`}
                      >
                        <input
                          type="radio"
                          name="chosenName"
                          checked={chosenName === name}
                          onChange={() => setChosenName(name)}
                          className="sr-only"
                        />
                        {name}
                      </label>
                    ))}
                  </div>
                </div>
              )}

              {/* Conflict resolution: source */}
              {preview.data.conflicts.source.length > 1 && (
                <div className="mb-5">
                  <h3 className="mb-2 text-sm font-medium text-surface-700">
                    Choose source
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {preview.data.conflicts.source.map((source: string) => (
                      <label
                        key={source}
                        className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-1.5 text-sm transition-colors ${
                          chosenSource === source
                            ? 'border-primary-300 bg-primary-50 text-primary-700'
                            : 'border-surface-200 text-surface-600 hover:bg-surface-50'
                        }`}
                      >
                        <input
                          type="radio"
                          name="chosenSource"
                          checked={chosenSource === source}
                          onChange={() => setChosenSource(source)}
                          className="sr-only"
                        />
                        {source}
                      </label>
                    ))}
                  </div>
                </div>
              )}

              {/* Totals summary */}
              <div className="rounded-lg border border-surface-200 bg-surface-50 p-4">
                <h3 className="mb-2 text-sm font-medium text-surface-700">
                  Combined totals after merge
                </h3>
                <div className="grid grid-cols-3 gap-x-6 gap-y-1 text-xs text-surface-600">
                  <span>Identifiers: {preview.data.totals.combined_identifiers}</span>
                  <span>Affiliations: {preview.data.totals.combined_affiliations}</span>
                  <span>Conversations: {preview.data.totals.conversations}</span>
                  <span>Relationships: {preview.data.totals.relationships}</span>
                  <span>Events: {preview.data.totals.events}</span>
                  <span>Phones: {preview.data.totals.phones}</span>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 border-t border-surface-200 px-6 py-4">
          <button
            onClick={onClose}
            className="rounded-md border border-surface-200 bg-white px-4 py-2 text-sm font-medium text-surface-600 hover:bg-surface-50"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={!survivingId || !preview.data || merge.isPending}
            className="flex items-center gap-2 rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {merge.isPending && <Loader2 size={14} className="animate-spin" />}
            Confirm Merge
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
