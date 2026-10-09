/** Drafts written here (MAIL-35), listed above the provider's drafts in
 * the Drafts folder. Clicking one resumes it in a docked composer. */

import { FileText, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { useCancelDraft, useListDrafts, type OutboundDraft } from '../../api/outbound.ts'
import { useComposeStore } from '../../stores/compose.ts'

function fmt(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
}

function toLine(d: OutboundDraft): string {
  const names = (d.to_addresses ?? []).map((r) => r.name || r.email).filter(Boolean)
  return names.length ? names.join(', ') : '(no recipient)'
}

export function LocalDrafts() {
  const drafts = useListDrafts()
  const resumeDraft = useComposeStore((s) => s.resumeDraft)
  const cancel = useCancelDraft()
  const items = drafts.data ?? []
  if (drafts.isLoading || items.length === 0) return null
  return (
    <section className="border-b border-surface-200 bg-surface-50" aria-label="Drafts written here">
      <div className="px-3 pt-1.5 text-[11px] font-semibold uppercase tracking-wider text-surface-500">Written here</div>
      <ul>
        {items.map((d) => (
          <li key={d.id} className="group flex items-center gap-2 px-3 py-1.5 hover:bg-surface-100">
            <button type="button" className="flex min-w-0 flex-1 items-center gap-2 text-left"
              onClick={() => { if (resumeDraft(d) === null) toast.info('Close a composer first (three are open)') }}>
              <FileText size={14} className="shrink-0 text-surface-400" />
              <span className="w-32 shrink-0 truncate text-sm text-surface-700">{toLine(d)}</span>
              <span className="min-w-0 flex-1 truncate text-sm text-surface-900">{d.subject || '(no subject)'}</span>
              <span className="shrink-0 text-xs text-surface-400">{fmt(d.updated_at)}</span>
            </button>
            <button type="button" aria-label={`Delete draft ${d.subject || ''}`} title="Delete draft"
              className="rounded p-0.5 text-surface-400 opacity-0 hover:text-red-600 group-hover:opacity-100"
              onClick={() => cancel.mutate(d.id)}>
              <Trash2 size={13} />
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
