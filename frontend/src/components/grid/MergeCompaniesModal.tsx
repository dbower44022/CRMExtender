import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { X, Loader2, AlertTriangle } from 'lucide-react'
import { toast } from 'sonner'
import { useCompanyMergePreview, useMergeCompanies } from '../../api/companies.ts'
import { useNavigationStore } from '../../stores/navigation.ts'
import type { CompanyMergePreviewCompany } from '../../types/api.ts'

interface MergeCompaniesModalProps {
  companyIds: string[]
  onClose: () => void
}

export function MergeCompaniesModal({ companyIds, onClose }: MergeCompaniesModalProps) {
  const deselectAllRows = useNavigationStore((s) => s.deselectAllRows)
  const preview = useCompanyMergePreview()
  const merge = useMergeCompanies()

  const [survivingId, setSurvivingId] = useState<string>('')

  useEffect(() => {
    preview.mutate(companyIds)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Set defaults when preview loads
  useEffect(() => {
    if (preview.data) {
      const companies = preview.data.companies
      if (companies.length > 0 && !survivingId) {
        setSurvivingId(companies[0].id)
      }
    }
  }, [preview.data]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleConfirm = () => {
    const absorbedIds = companyIds.filter((id) => id !== survivingId)
    merge.mutate(
      {
        surviving_id: survivingId,
        absorbed_ids: absorbedIds,
      },
      {
        onSuccess: (result) => {
          const count = result.absorbed_ids.length
          toast.success(
            `Merged ${count} compan${count > 1 ? 'ies' : 'y'} successfully. ` +
            `${result.contacts_reassigned} contacts, ` +
            `${result.relationships_reassigned} relationships transferred.`
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
            Merge {companyIds.length} Companies
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
              {/* Surviving company selection */}
              <div className="mb-5">
                <h3 className="mb-2 text-sm font-medium text-surface-700">
                  Select surviving company
                </h3>
                <p className="mb-3 text-xs text-surface-500">
                  All data from other companies will be transferred to the surviving company.
                  The other companies will be deleted.
                </p>
                <div className="space-y-2">
                  {preview.data.companies.map((company: CompanyMergePreviewCompany) => (
                    <label
                      key={company.id}
                      className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors ${
                        survivingId === company.id
                          ? 'border-primary-300 bg-primary-50'
                          : 'border-surface-200 hover:bg-surface-50'
                      }`}
                    >
                      <input
                        type="radio"
                        name="surviving"
                        checked={survivingId === company.id}
                        onChange={() => setSurvivingId(company.id)}
                        className="mt-0.5"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-surface-900">
                            {company.name}
                          </span>
                          {company.domain && (
                            <span className="rounded bg-surface-100 px-1.5 py-0.5 text-[10px] text-surface-500">
                              {company.domain}
                            </span>
                          )}
                          {company.industry && (
                            <span className="rounded bg-surface-100 px-1.5 py-0.5 text-[10px] text-surface-500">
                              {company.industry}
                            </span>
                          )}
                        </div>
                        <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-surface-500">
                          <span>{company.contact_count} contacts</span>
                          <span>{company.identifier_count} identifiers</span>
                          <span>{company.relationship_count} relationships</span>
                          <span>{company.event_count} events</span>
                        </div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              {/* Conflicts info */}
              {(preview.data.conflicts.name.length > 1 ||
                preview.data.conflicts.domain.length > 1 ||
                preview.data.conflicts.industry.length > 1) && (
                <div className="mb-5 rounded-md border border-amber-200 bg-amber-50 p-3">
                  <h3 className="mb-1 text-sm font-medium text-amber-800">
                    Field differences
                  </h3>
                  <p className="mb-2 text-xs text-amber-700">
                    The surviving company's values will be kept. Empty fields will be backfilled
                    from absorbed companies.
                  </p>
                  <div className="space-y-1 text-xs text-amber-700">
                    {preview.data.conflicts.name.length > 1 && (
                      <div>Names: {preview.data.conflicts.name.join(', ')}</div>
                    )}
                    {preview.data.conflicts.domain.length > 1 && (
                      <div>Domains: {preview.data.conflicts.domain.join(', ')}</div>
                    )}
                    {preview.data.conflicts.industry.length > 1 && (
                      <div>Industries: {preview.data.conflicts.industry.join(', ')}</div>
                    )}
                  </div>
                </div>
              )}

              {/* Totals summary */}
              <div className="rounded-lg border border-surface-200 bg-surface-50 p-4">
                <h3 className="mb-2 text-sm font-medium text-surface-700">
                  Combined totals after merge
                </h3>
                <div className="grid grid-cols-3 gap-x-6 gap-y-1 text-xs text-surface-600">
                  <span>Contacts: {preview.data.totals.contacts}</span>
                  <span>Identifiers: {preview.data.totals.identifiers}</span>
                  <span>Relationships: {preview.data.totals.relationships}</span>
                  <span>Events: {preview.data.totals.events}</span>
                  <span>Phones: {preview.data.totals.phones}</span>
                  <span>Addresses: {preview.data.totals.addresses}</span>
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
