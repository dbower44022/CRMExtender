import { Link2, Plus, Briefcase, Building2, User, Calendar } from 'lucide-react'
import { formatTimestamp } from '../../lib/formatTimestamp.ts'
import { useNavigationStore } from '../../stores/navigation.ts'
import type { ConversationAssociations } from '../../types/api.ts'

interface ConversationAssociationsCardProps {
  associations: ConversationAssociations
  onNavigateAway: () => void
}

export function ConversationAssociationsCard({ associations, onNavigateAway }: ConversationAssociationsCardProps) {
  const setActiveEntityType = useNavigationStore((s) => s.setActiveEntityType)
  const setSelectedRow = useNavigationStore((s) => s.setSelectedRow)

  const { projects, companies, contacts, events } = associations
  const totalCount = projects.length + companies.length + contacts.length + events.length

  // Suppressed when no associations exist (PRD Section 10.3)
  if (totalCount === 0) return null

  const navigateTo = (entityType: string, entityId: string) => {
    setActiveEntityType(entityType)
    setSelectedRow(entityId, -1)
    onNavigateAway()
  }

  return (
    <div className="rounded-lg border border-surface-200 bg-white">
      <div className="flex items-center justify-between border-b border-surface-200 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Link2 size={14} className="text-surface-400" />
          <span className="text-xs font-semibold uppercase text-surface-500">
            Associations
          </span>
        </div>
        <button
          disabled
          className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs text-surface-300"
          title="Link entity (coming soon)"
        >
          <Plus size={12} />
          Link
        </button>
      </div>

      <div className="divide-y divide-surface-100">
        {/* Projects group */}
        {projects.length > 0 && (
          <div className="px-4 py-2.5">
            <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-surface-400">
              <Briefcase size={12} />
              Projects
            </div>
            <div className="space-y-1.5">
              {projects.map((p) => (
                <div key={p.relationship_id} className="flex items-center justify-between gap-2">
                  <button
                    className="truncate text-sm text-primary-600 hover:underline"
                    onClick={() => navigateTo('project', p.id)}
                  >
                    {p.name}
                  </button>
                  {p.status && (
                    <span className="shrink-0 rounded bg-surface-100 px-1.5 py-0.5 text-xs capitalize text-surface-500">
                      {p.status}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Companies group */}
        {companies.length > 0 && (
          <div className="px-4 py-2.5">
            <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-surface-400">
              <Building2 size={12} />
              Companies
            </div>
            <div className="space-y-1.5">
              {companies.map((c) => (
                <button
                  key={c.relationship_id}
                  className="block truncate text-sm text-primary-600 hover:underline"
                  onClick={() => navigateTo('company', c.id)}
                >
                  {c.name}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Contacts group — explicit associations, NOT derived participants */}
        {contacts.length > 0 && (
          <div className="px-4 py-2.5">
            <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-surface-400">
              <User size={12} />
              Contacts
            </div>
            <div className="space-y-1.5">
              {contacts.map((c) => (
                <div key={c.relationship_id}>
                  <button
                    className="truncate text-sm text-primary-600 hover:underline"
                    onClick={() => navigateTo('contact', c.id)}
                  >
                    {c.name}
                  </button>
                  {(c.title || c.company_name) && (
                    <div className="text-xs text-surface-400">
                      {[c.title, c.company_name].filter(Boolean).join(' · ')}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Events group */}
        {events.length > 0 && (
          <div className="px-4 py-2.5">
            <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-surface-400">
              <Calendar size={12} />
              Events
            </div>
            <div className="space-y-1.5">
              {events.map((e) => (
                <div key={e.relationship_id} className="flex items-center justify-between gap-2">
                  <button
                    className="truncate text-sm text-primary-600 hover:underline"
                    onClick={() => navigateTo('event', e.id)}
                  >
                    {e.title || 'Untitled Event'}
                  </button>
                  {e.start_datetime && (
                    <span className="shrink-0 text-xs text-surface-400">
                      {formatTimestamp(e.start_datetime)}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
