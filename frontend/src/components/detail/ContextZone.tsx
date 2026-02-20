import { Building2, Link2, Tag } from 'lucide-react'

interface ContextZoneProps {
  data: Record<string, unknown>
}

export function ContextZone({ data }: ContextZoneProps) {
  const affiliations = (data.affiliations as Array<{
    company_name: string
    company_id: string
    role_name?: string
    title?: string
    is_current?: boolean
  }>) ?? []

  const relationships = (data.relationships as Array<{
    other_name: string
    other_id: string
    other_entity_type: string
    label: string
  }>) ?? []

  const tags = (data.tags as string[]) ?? []

  const hasContent =
    affiliations.length > 0 || relationships.length > 0 || tags.length > 0

  if (!hasContent) return null

  return (
    <div className="border-b border-surface-200 p-4">
      {affiliations.length > 0 && (
        <div className="mb-3">
          <h4 className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-surface-500 uppercase">
            <Building2 size={12} />
            Affiliations
          </h4>
          <div className="space-y-1">
            {affiliations.map((a, i) => (
              <div key={i} className="flex items-center justify-between text-sm">
                <a
                  href={`/companies/${a.company_id}`}
                  className="text-primary-600 hover:underline"
                >
                  {a.company_name}
                </a>
                <span className="text-xs text-surface-400">
                  {a.title || a.role_name}
                  {a.is_current === false && ' (former)'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {relationships.length > 0 && (
        <div className="mb-3">
          <h4 className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-surface-500 uppercase">
            <Link2 size={12} />
            Relationships
          </h4>
          <div className="space-y-1">
            {relationships.map((r, i) => (
              <div key={i} className="flex items-center justify-between text-sm">
                <a
                  href={`/${r.other_entity_type}s/${r.other_id}`}
                  className="text-primary-600 hover:underline"
                >
                  {r.other_name}
                </a>
                <span className="text-xs text-surface-400">{r.label}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {tags.length > 0 && (
        <div>
          <h4 className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-surface-500 uppercase">
            <Tag size={12} />
            Tags
          </h4>
          <div className="flex flex-wrap gap-1">
            {tags.map((t) => (
              <span
                key={t}
                className="rounded-full bg-surface-100 px-2 py-0.5 text-xs text-surface-600"
              >
                {t}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
