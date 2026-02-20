import {
  User,
  Building2,
  MessageSquare,
  Calendar,
  ExternalLink,
  Mail,
  Phone,
  MapPin,
} from 'lucide-react'

const ENTITY_ICONS: Record<string, typeof User> = {
  contact: User,
  company: Building2,
  conversation: MessageSquare,
  event: Calendar,
}

interface IdentityZoneProps {
  data: Record<string, unknown>
  entityType: string
  entityId: string
}

export function IdentityZone({ data, entityType, entityId }: IdentityZoneProps) {
  const Icon = ENTITY_ICONS[entityType] ?? User
  const name = String(data.name ?? data.title ?? 'Untitled')
  const subtitle = data.subtitle ? String(data.subtitle) : null
  const emails = (data.emails as string[] | undefined) ?? []
  const phones = (data.phones as string[] | undefined) ?? []
  const addresses = (data.addresses as string[] | undefined) ?? []
  const company = data.company as
    | { name: string; id: string }
    | undefined

  const htmxDetailUrl = entityType === 'conversation'
    ? `/conversations/${entityId}`
    : entityType === 'event'
      ? `/events/${entityId}`
      : entityType === 'company'
        ? `/companies/${entityId}`
        : `/contacts/${entityId}`

  return (
    <div className="border-b border-surface-200 p-4">
      <div className="mb-2 flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary-50 text-primary-600">
          <Icon size={18} />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-base font-semibold text-surface-900">
            {name}
          </h3>
          {subtitle && (
            <p className="truncate text-sm text-surface-500">{subtitle}</p>
          )}
        </div>
        <a
          href={htmxDetailUrl}
          title="Open full detail"
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded text-surface-400 transition-colors hover:bg-surface-100 hover:text-surface-600"
        >
          <ExternalLink size={14} />
        </a>
      </div>

      {company && (
        <a
          href={`/companies/${company.id}`}
          className="mb-2 inline-flex items-center gap-1 text-sm text-primary-600 hover:underline"
        >
          <Building2 size={12} />
          {company.name}
        </a>
      )}

      <div className="space-y-1">
        {emails.map((email) => (
          <div key={email} className="flex items-center gap-2 text-sm text-surface-600">
            <Mail size={12} className="shrink-0 text-surface-400" />
            <span className="truncate">{email}</span>
          </div>
        ))}
        {phones.map((phone) => (
          <div key={phone} className="flex items-center gap-2 text-sm text-surface-600">
            <Phone size={12} className="shrink-0 text-surface-400" />
            <span>{phone}</span>
          </div>
        ))}
        {addresses.map((addr, i) => (
          <div key={i} className="flex items-start gap-2 text-sm text-surface-600">
            <MapPin size={12} className="mt-0.5 shrink-0 text-surface-400" />
            <span className="whitespace-pre-line">{addr}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
