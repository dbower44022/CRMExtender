/** Relationship context beside the reading pane (MAIL-32; PRD §2.8).
 *
 * For the thread's external participants: the contact card (name, title,
 * company, relationship score), recent conversations with their summaries,
 * and a link to the full contact. Unknown senders get a "Create contact"
 * affordance. The thread's own CRM conversation summary sits on top.
 */

import { useState } from 'react'
import { useQueries } from '@tanstack/react-query'
import { ExternalLink, UserPlus } from 'lucide-react'
import { get } from '../../api/client.ts'
import type { ThreadDetail } from '../../api/mail.ts'
import { externalParticipants, type ExternalParticipant } from '../../lib/mailParticipants.ts'
import { useNavigationStore } from '../../stores/navigation.ts'
import { AddContactModal } from '../grid/AddContactModal.tsx'

interface ContactDetail {
  identity: {
    name: string
    subtitle: string | null
    company: { id: string; name: string } | null
    score: number | null
    status: string | null
  }
  context: { affiliations: { company_name: string | null; title: string | null; is_current: boolean }[] }
  timeline: { type: string; id: string; title: string; date: string; summary: string | null }[]
}

function fmtDate(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })
}

function ContactCard({ p, detail, loading }: { p: ExternalParticipant; detail: ContactDetail | undefined; loading: boolean }) {
  const openContact = useNavigationStore((s) => s.setPendingNavigation)
  const setActiveEntityType = useNavigationStore((s) => s.setActiveEntityType)
  const go = () => {
    if (!p.contact_id) return
    setActiveEntityType('contact')
    openContact({ entityType: 'contact', entityId: p.contact_id })
  }
  const name = detail?.identity.name || p.contact_name || p.name || p.address
  const aff = detail?.context.affiliations.find((a) => a.is_current) ?? detail?.context.affiliations[0]
  const convs = (detail?.timeline ?? []).filter((x) => x.type === 'conversation').slice(0, 2)
  return (
    <section className="rounded-md border border-surface-200 bg-surface-0 p-2.5">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-surface-900">{name}</div>
          <div className="truncate text-xs text-surface-500">{p.address}</div>
          {(aff?.title || aff?.company_name || detail?.identity.company) && (
            <div className="mt-0.5 truncate text-xs text-surface-700">
              {[aff?.title, aff?.company_name || detail?.identity.company?.name].filter(Boolean).join(' · ')}
            </div>
          )}
        </div>
        {detail?.identity.score != null && (
          <span className="shrink-0 rounded bg-primary-50 px-1.5 py-0.5 text-[11px] font-semibold text-primary-800" title="Relationship score">
            {Math.round(detail.identity.score)}
          </span>
        )}
      </div>
      {loading && <div className="mt-1 text-[11px] text-surface-400">Loading…</div>}
      {convs.length > 0 && (
        <ul className="mt-2 space-y-1 border-t border-surface-100 pt-2">
          {convs.map((c) => (
            <li key={c.id} className="text-xs">
              <div className="flex justify-between gap-2">
                <span className="truncate text-surface-800">{c.title}</span>
                <span className="shrink-0 text-surface-400">{fmtDate(c.date)}</span>
              </div>
              {c.summary && <div className="line-clamp-2 text-surface-500">{c.summary}</div>}
            </li>
          ))}
        </ul>
      )}
      {p.contact_id && (
        <button type="button" onClick={go} className="mt-2 inline-flex items-center gap-1 text-xs text-primary-700 hover:underline">
          <ExternalLink size={11} /> Open contact
        </button>
      )}
    </section>
  )
}

export function ContextColumn({ thread }: { thread: ThreadDetail }) {
  const people = externalParticipants(thread)
  const [adding, setAdding] = useState(false)
  const details = useQueries({
    queries: people.map((p) => ({
      queryKey: ['contact-detail', p.contact_id],
      queryFn: () => get<ContactDetail>(`/contacts/${encodeURIComponent(p.contact_id!)}`),
      enabled: !!p.contact_id,
      staleTime: 60_000,
    })),
  })
  const unknown = people.filter((p) => !p.contact_id)
  return (
    <aside className="flex w-72 shrink-0 flex-col gap-2 overflow-y-auto border-l border-surface-200 bg-surface-50 p-2" aria-label="Relationship context">
      {thread.conversation && (
        <section className="rounded-md border border-surface-200 bg-surface-0 p-2.5">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-surface-500">Conversation</div>
          <div className="mt-0.5 text-sm font-medium text-surface-900">{thread.conversation.title || 'Untitled'}</div>
          {thread.conversation.ai_status && (
            <span className="mt-1 inline-block rounded bg-surface-100 px-1 text-[10px] uppercase tracking-wide text-surface-600">{thread.conversation.ai_status}</span>
          )}
          {thread.conversation.ai_summary && <p className="mt-1 text-xs text-surface-700">{thread.conversation.ai_summary}</p>}
        </section>
      )}
      {people.length === 0 && <div className="px-1 text-xs text-surface-500">No external participants.</div>}
      {people.map((p, i) => (
        <ContactCard key={p.address} p={p} detail={details[i]?.data} loading={!!details[i]?.isLoading} />
      ))}
      {unknown.length > 0 && (
        <div className="px-1">
          <button type="button" onClick={() => setAdding(true)} className="inline-flex items-center gap-1 text-xs text-primary-700 hover:underline">
            <UserPlus size={12} /> Create contact for {unknown[0].name || unknown[0].address}
          </button>
        </div>
      )}
      {adding && <AddContactModal onClose={() => setAdding(false)} />}
    </aside>
  )
}
