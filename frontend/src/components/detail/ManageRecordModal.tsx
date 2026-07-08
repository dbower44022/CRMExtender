import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Loader2, Plus, Star, Trash2, X } from 'lucide-react'
import { toast } from 'sonner'
import { get, put } from '../../api/client.ts'
import {
  sub,
  useInvalidateRecord,
  useSubresources,
  type AddressRow,
  type ContactCore,
  type Subresources,
} from '../../api/subresources.ts'

interface ManageRecordModalProps {
  entityType: 'contact' | 'company'
  entityId: string
  entityName: string
  onClose: () => void
}

/** Sub-resource editing for a contact or company (UI Migration Phase 2). */
export function ManageRecordModal({
  entityType,
  entityId,
  entityName,
  onClose,
}: ManageRecordModalProps) {
  const { data, isLoading } = useSubresources(entityType, entityId)
  const invalidate = useInvalidateRecord(entityType, entityId)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  const run = async (label: string, fn: () => Promise<unknown>) => {
    try {
      await fn()
      invalidate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : `${label} failed`)
    }
  }

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="relative mx-4 flex max-h-[85vh] w-full max-w-xl flex-col rounded-lg bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-surface-200 px-6 py-4">
          <h2 className="truncate text-lg font-semibold text-surface-900">
            Manage {entityName}
          </h2>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-surface-400 hover:bg-surface-100 hover:text-surface-600"
          >
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 space-y-6 overflow-y-auto px-6 py-4">
          {isLoading || !data ? (
            <div className="flex items-center gap-2 py-8 text-sm text-surface-400">
              <Loader2 size={16} className="animate-spin" /> Loading…
            </div>
          ) : entityType === 'contact' ? (
            <ContactSections data={data} entityId={entityId} run={run} />
          ) : (
            <CompanySections data={data} entityId={entityId} run={run} />
          )}
        </div>
      </div>
    </div>,
    document.body,
  )
}

type Run = (label: string, fn: () => Promise<unknown>) => Promise<void>

/* ------------------------------------------------------------------ */

const LEAD_STATUSES = ['new', 'contacted', 'qualified', 'nurturing',
                       'customer', 'lost', 'inactive']

function CoreFieldsSection({ entityId, core, run }: {
  entityId: string
  core: ContactCore
  run: Run
}) {
  const [first, setFirst] = useState(core.first_name ?? '')
  const [last, setLast] = useState(core.last_name ?? '')
  const [name, setName] = useState(core.name ?? '')
  const [leadStatus, setLeadStatus] = useState(core.lead_status ?? 'new')
  const [dirty, setDirty] = useState(false)

  const inputCls =
    'w-full rounded-md border border-surface-300 px-2 py-1 text-sm focus:border-primary-400 focus:outline-none'
  const computed = [first.trim(), last.trim()].filter(Boolean).join(' ')
  const overridden = name.trim() !== '' && name.trim() !== computed

  const save = () => run('Save details', async () => {
    const body: Record<string, unknown> = {
      first_name: first,
      last_name: last,
      lead_status: leadStatus,
    }
    // Only send name when the user has overridden the computed value —
    // otherwise the backend recomputes it from first/last
    if (overridden) body.name = name.trim()
    await put(`/contacts/${entityId}`, body)
    setDirty(false)
  })

  return (
    <Section title="Details">
      <div className="space-y-2">
        <div className="flex gap-2">
          <input value={first} placeholder="First name"
            onChange={(e) => { setFirst(e.target.value); setDirty(true) }}
            className={inputCls} />
          <input value={last} placeholder="Last name"
            onChange={(e) => { setLast(e.target.value); setDirty(true) }}
            className={inputCls} />
        </div>
        <div>
          <input value={name} placeholder={computed || 'Display name'}
            onChange={(e) => { setName(e.target.value); setDirty(true) }}
            className={inputCls} />
          <div className="mt-0.5 text-xs text-surface-400">
            {overridden
              ? 'Display name is overridden'
              : 'Display name follows first + last'}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <select value={leadStatus}
            onChange={(e) => { setLeadStatus(e.target.value); setDirty(true) }}
            className="flex-1 rounded-md border border-surface-300 px-2 py-1 text-sm">
            {LEAD_STATUSES.map((v) => (
              <option key={v} value={v}>Lead: {v}</option>
            ))}
          </select>
          <button
            onClick={save}
            disabled={!dirty || (!first.trim() && !last.trim() && !name.trim())}
            className="rounded-md bg-primary-600 px-3 py-1 text-xs font-medium text-white hover:bg-primary-700 disabled:opacity-50"
          >
            Save
          </button>
        </div>
      </div>
    </Section>
  )
}


function ContactSections({ data, entityId, run }: {
  data: Subresources
  entityId: string
  run: Run
}) {
  const emails = data.identifiers.filter((i) => i.type === 'email')
  const otherIds = data.identifiers.filter((i) => i.type !== 'email')
  return (
    <>
      {data.core && (
        <CoreFieldsSection entityId={entityId} core={data.core} run={run} />
      )}
      <Section title="Emails">
        <RowList
          rows={emails.map((e) => ({
            id: e.id,
            label: e.value,
            sub: e.label || null,
            isPrimary: !!e.is_primary,
          }))}
          onPrimary={(id) => run('Set primary', () =>
            sub.update('contact', entityId, 'identifiers', id, { is_primary: true }))}
          onDelete={(id) => run('Delete', () =>
            sub.remove('contact', entityId, 'identifiers', id))}
        />
        <AddInline placeholder="new@email.com" buttonLabel="Add email"
          onAdd={(value) => run('Add email', () =>
            sub.add('contact', entityId, 'identifiers', { type: 'email', value }))} />
      </Section>

      <PhoneSection entityType="contact" entityId={entityId} data={data} run={run} />
      <AddressSection entityType="contact" entityId={entityId} data={data} run={run} />

      <Section title="Affiliations">
        <RowList
          rows={(data.affiliations ?? []).map((a) => ({
            id: a.id,
            label: a.company_name,
            sub: [a.title, a.role_name].filter(Boolean).join(' · ') || null,
            isPrimary: !!a.is_primary,
            muted: !a.is_current,
          }))}
          onPrimary={(id) => run('Set primary', () =>
            sub.update('contact', entityId, 'affiliations', id, { is_primary: true }))}
          onDelete={(id) => run('Delete', () =>
            sub.remove('contact', entityId, 'affiliations', id))}
        />
        <AffiliationAdd entityId={entityId} run={run} />
      </Section>

      {otherIds.length > 0 && (
        <Section title="Other Identifiers">
          <RowList
            rows={otherIds.map((i) => ({
              id: i.id,
              label: i.value,
              sub: i.type,
              isPrimary: !!i.is_primary,
            }))}
            onDelete={(id) => run('Delete', () =>
              sub.remove('contact', entityId, 'identifiers', id))}
          />
        </Section>
      )}
    </>
  )
}

function CompanySections({ data, entityId, run }: {
  data: Subresources
  entityId: string
  run: Run
}) {
  return (
    <>
      <Section title="Identifiers (domains)">
        <RowList
          rows={data.identifiers.map((i) => ({
            id: i.id,
            label: i.value,
            sub: i.type,
            isPrimary: !!i.is_primary,
          }))}
          onDelete={(id) => run('Delete', () =>
            sub.remove('company', entityId, 'identifiers', id))}
        />
        <AddInline placeholder="example.com" buttonLabel="Add domain"
          onAdd={(value) => run('Add identifier', () =>
            sub.add('company', entityId, 'identifiers', { type: 'domain', value }))} />
      </Section>

      <Section title="Emails">
        <RowList
          rows={(data.emails ?? []).map((e) => ({
            id: e.id,
            label: e.address,
            sub: e.email_type,
            isPrimary: !!e.is_primary,
          }))}
          onPrimary={(id) => run('Set primary', () =>
            sub.update('company', entityId, 'emails', id, { is_primary: true }))}
          onDelete={(id) => run('Delete', () =>
            sub.remove('company', entityId, 'emails', id))}
        />
        <AddInline placeholder="info@example.com" buttonLabel="Add email"
          onAdd={(value) => run('Add email', () =>
            sub.add('company', entityId, 'emails', { address: value }))} />
      </Section>

      <PhoneSection entityType="company" entityId={entityId} data={data} run={run} />
      <AddressSection entityType="company" entityId={entityId} data={data} run={run} />
      <HierarchySection entityId={entityId} data={data} run={run} />
    </>
  )
}

/* ------------------------------------------------------------------ */

function PhoneSection({ entityType, entityId, data, run }: {
  entityType: string
  entityId: string
  data: Subresources
  run: Run
}) {
  return (
    <Section title="Phones">
      <RowList
        rows={data.phones.map((p) => ({
          id: p.id,
          label: p.display,
          sub: p.phone_type,
          isPrimary: !!p.is_primary,
          muted: !p.is_current,
        }))}
        onPrimary={(id) => run('Set primary', () =>
          sub.update(entityType, entityId, 'phones', id, { is_primary: true }))}
        onDelete={(id) => run('Delete', () =>
          sub.remove(entityType, entityId, 'phones', id))}
      />
      <AddInline placeholder="(330) 555-0100" buttonLabel="Add phone"
        onAdd={(value) => run('Add phone', () =>
          sub.add(entityType, entityId, 'phones', { number: value }))} />
    </Section>
  )
}

function formatAddr(a: AddressRow): string {
  return [a.street, a.city, a.state, a.postal_code, a.country]
    .filter(Boolean).join(', ')
}

function AddressSection({ entityType, entityId, data, run }: {
  entityType: string
  entityId: string
  data: Subresources
  run: Run
}) {
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState({ street: '', city: '', state: '', postal_code: '', country: '' })

  const submit = async () => {
    await run('Add address', () => sub.add(entityType, entityId, 'addresses', form))
    setForm({ street: '', city: '', state: '', postal_code: '', country: '' })
    setAdding(false)
  }

  const field = (key: keyof typeof form, placeholder: string, cls = '') => (
    <input
      value={form[key]}
      onChange={(e) => setForm({ ...form, [key]: e.target.value })}
      placeholder={placeholder}
      className={`rounded-md border border-surface-300 px-2 py-1 text-sm focus:border-primary-400 focus:outline-none ${cls}`}
    />
  )

  return (
    <Section title="Addresses">
      <RowList
        rows={data.addresses.map((a) => ({
          id: a.id,
          label: formatAddr(a) || '(empty address)',
          sub: a.address_type,
          isPrimary: !!a.is_primary,
          muted: !a.is_current,
        }))}
        onPrimary={(id) => run('Set primary', () =>
          sub.update(entityType, entityId, 'addresses', id, { is_primary: true }))}
        onDelete={(id) => run('Delete', () =>
          sub.remove(entityType, entityId, 'addresses', id))}
      />
      {adding ? (
        <div className="mt-2 space-y-2">
          {field('street', 'Street', 'w-full')}
          <div className="flex gap-2">
            {field('city', 'City', 'flex-1')}
            {field('state', 'State', 'w-16')}
            {field('postal_code', 'ZIP', 'w-24')}
            {field('country', 'Country', 'w-20')}
          </div>
          <div className="flex gap-2">
            <button onClick={submit}
              className="rounded-md bg-primary-600 px-3 py-1 text-xs font-medium text-white hover:bg-primary-700">
              Save address
            </button>
            <button onClick={() => setAdding(false)}
              className="rounded-md px-3 py-1 text-xs text-surface-500 hover:bg-surface-100">
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <AddButton label="Add address" onClick={() => setAdding(true)} />
      )}
    </Section>
  )
}

function AffiliationAdd({ entityId, run }: { entityId: string; run: Run }) {
  const [adding, setAdding] = useState(false)
  const [title, setTitle] = useState('')
  const [company, setCompany] = useState<{ id: string; name: string } | null>(null)

  const submit = async () => {
    if (!company) return
    await run('Add affiliation', () =>
      sub.add('contact', entityId, 'affiliations', {
        company_id: company.id, title: title || undefined,
      }))
    setCompany(null)
    setTitle('')
    setAdding(false)
  }

  if (!adding) return <AddButton label="Add affiliation" onClick={() => setAdding(true)} />
  return (
    <div className="mt-2 space-y-2">
      <CompanyPicker value={company} onChange={setCompany} />
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Title (optional)"
        className="w-full rounded-md border border-surface-300 px-2 py-1 text-sm focus:border-primary-400 focus:outline-none"
      />
      <div className="flex gap-2">
        <button onClick={submit} disabled={!company}
          className="rounded-md bg-primary-600 px-3 py-1 text-xs font-medium text-white hover:bg-primary-700 disabled:opacity-50">
          Save affiliation
        </button>
        <button onClick={() => setAdding(false)}
          className="rounded-md px-3 py-1 text-xs text-surface-500 hover:bg-surface-100">
          Cancel
        </button>
      </div>
    </div>
  )
}

function HierarchySection({ entityId, data, run }: {
  entityId: string
  data: Subresources
  run: Run
}) {
  const [adding, setAdding] = useState(false)
  const [related, setRelated] = useState<{ id: string; name: string } | null>(null)
  const [direction, setDirection] = useState<'parent' | 'child'>('parent')
  const [hierarchyType, setHierarchyType] = useState('subsidiary')

  const h = data.hierarchy ?? { parents: [], children: [] }
  const rows = [
    ...h.parents.map((r) => ({
      id: r.id, label: `Parent: ${r.parent_name}`, sub: r.hierarchy_type,
      isPrimary: false,
    })),
    ...h.children.map((r) => ({
      id: r.id, label: `Child: ${r.child_name}`, sub: r.hierarchy_type,
      isPrimary: false,
    })),
  ]

  const submit = async () => {
    if (!related) return
    await run('Add relationship', () =>
      sub.add('company', entityId, 'hierarchy', {
        related_company_id: related.id, direction, hierarchy_type: hierarchyType,
      }))
    setRelated(null)
    setAdding(false)
  }

  return (
    <Section title="Company Hierarchy">
      <RowList rows={rows}
        onDelete={(id) => run('Delete', () =>
          sub.remove('company', entityId, 'hierarchy', id))} />
      {adding ? (
        <div className="mt-2 space-y-2">
          <CompanyPicker value={related} onChange={setRelated} excludeId={entityId} />
          <div className="flex gap-2">
            <select value={direction}
              onChange={(e) => setDirection(e.target.value as 'parent' | 'child')}
              className="rounded-md border border-surface-300 px-2 py-1 text-sm">
              <option value="parent">Is our parent</option>
              <option value="child">Is our child</option>
            </select>
            <select value={hierarchyType}
              onChange={(e) => setHierarchyType(e.target.value)}
              className="rounded-md border border-surface-300 px-2 py-1 text-sm">
              <option value="subsidiary">Subsidiary</option>
              <option value="division">Division</option>
              <option value="acquisition">Acquisition</option>
              <option value="spinoff">Spinoff</option>
            </select>
          </div>
          <div className="flex gap-2">
            <button onClick={submit} disabled={!related}
              className="rounded-md bg-primary-600 px-3 py-1 text-xs font-medium text-white hover:bg-primary-700 disabled:opacity-50">
              Save
            </button>
            <button onClick={() => setAdding(false)}
              className="rounded-md px-3 py-1 text-xs text-surface-500 hover:bg-surface-100">
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <AddButton label="Add hierarchy link" onClick={() => setAdding(true)} />
      )}
    </Section>
  )
}

/* ------------------------------------------------------------------ */
/* Shared pieces                                                       */

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-surface-500">
        {title}
      </h3>
      {children}
    </div>
  )
}

interface Row {
  id: string
  label: string
  sub: string | null
  isPrimary: boolean
  muted?: boolean
}

function RowList({ rows, onPrimary, onDelete }: {
  rows: Row[]
  onPrimary?: (id: string) => void
  onDelete: (id: string) => void
}) {
  const [confirming, setConfirming] = useState<string | null>(null)
  if (rows.length === 0) {
    return <div className="py-1 text-sm italic text-surface-300">None</div>
  }
  return (
    <ul className="divide-y divide-surface-100 rounded-md border border-surface-200">
      {rows.map((row) => (
        <li key={row.id}
          className={`flex items-center gap-2 px-3 py-1.5 ${row.muted ? 'opacity-50' : ''}`}>
          <span className="min-w-0 flex-1 truncate text-sm text-surface-800">
            {row.label}
          </span>
          {row.sub && (
            <span className="shrink-0 text-xs text-surface-400">{row.sub}</span>
          )}
          {onPrimary && (
            <button
              title={row.isPrimary ? 'Primary' : 'Set as primary'}
              onClick={() => !row.isPrimary && onPrimary(row.id)}
              className={`shrink-0 rounded p-1 ${
                row.isPrimary
                  ? 'text-amber-500'
                  : 'text-surface-300 hover:bg-surface-100 hover:text-amber-500'
              }`}
            >
              <Star size={13} fill={row.isPrimary ? 'currentColor' : 'none'} />
            </button>
          )}
          {confirming === row.id ? (
            <button
              onClick={() => { onDelete(row.id); setConfirming(null) }}
              onBlur={() => setConfirming(null)}
              className="shrink-0 rounded bg-red-600 px-2 py-0.5 text-xs font-medium text-white"
            >
              Confirm
            </button>
          ) : (
            <button
              title="Delete"
              onClick={() => setConfirming(row.id)}
              className="shrink-0 rounded p-1 text-surface-300 hover:bg-red-50 hover:text-red-600"
            >
              <Trash2 size={13} />
            </button>
          )}
        </li>
      ))}
    </ul>
  )
}

function AddButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button onClick={onClick}
      className="mt-2 flex items-center gap-1 text-xs font-medium text-primary-600 hover:text-primary-700">
      <Plus size={12} /> {label}
    </button>
  )
}

function AddInline({ placeholder, buttonLabel, onAdd }: {
  placeholder: string
  buttonLabel: string
  onAdd: (value: string) => Promise<void> | void
}) {
  const [open, setOpen] = useState(false)
  const [value, setValue] = useState('')

  const submit = async () => {
    if (!value.trim()) return
    await onAdd(value.trim())
    setValue('')
    setOpen(false)
  }

  if (!open) return <AddButton label={buttonLabel} onClick={() => setOpen(true)} />
  return (
    <div className="mt-2 flex gap-2">
      <input
        autoFocus
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') submit() }}
        placeholder={placeholder}
        className="flex-1 rounded-md border border-surface-300 px-2 py-1 text-sm focus:border-primary-400 focus:outline-none"
      />
      <button onClick={submit}
        className="rounded-md bg-primary-600 px-3 py-1 text-xs font-medium text-white hover:bg-primary-700">
        Add
      </button>
      <button onClick={() => setOpen(false)}
        className="rounded-md px-2 py-1 text-xs text-surface-500 hover:bg-surface-100">
        Cancel
      </button>
    </div>
  )
}

interface SearchHit { id: string; name: string }

function CompanyPicker({ value, onChange, excludeId }: {
  value: SearchHit | null
  onChange: (v: SearchHit | null) => void
  excludeId?: string
}) {
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState<SearchHit[]>([])

  useEffect(() => {
    const t = setTimeout(async () => {
      if (query.length < 2) {
        setHits([])
        return
      }
      try {
        const res = await get<{
          groups: { entity_type: string; results: { id: string; name: string }[] }[]
        }>(`/search?q=${encodeURIComponent(query)}&entity_type=company&limit=8`)
        const companies = res.groups.find((g) => g.entity_type === 'company')
        setHits(
          (companies?.results ?? [])
            .filter((r) => r.id !== excludeId)
            .map((r) => ({ id: r.id, name: r.name })),
        )
      } catch {
        setHits([])
      }
    }, 250)
    return () => clearTimeout(t)
  }, [query, excludeId])

  if (value) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-surface-200 bg-surface-50 px-2 py-1 text-sm">
        <span className="flex-1 truncate">{value.name}</span>
        <button onClick={() => onChange(null)}
          className="text-surface-400 hover:text-surface-600">
          <X size={13} />
        </button>
      </div>
    )
  }
  return (
    <div className="relative">
      <input
        autoFocus
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search companies…"
        className="w-full rounded-md border border-surface-300 px-2 py-1 text-sm focus:border-primary-400 focus:outline-none"
      />
      {hits.length > 0 && (
        <ul className="absolute z-10 mt-1 max-h-40 w-full overflow-y-auto rounded-md border border-surface-200 bg-white shadow-lg">
          {hits.map((h) => (
            <li key={h.id}>
              <button
                onClick={() => { onChange(h); setQuery('') }}
                className="w-full px-3 py-1.5 text-left text-sm hover:bg-surface-50"
              >
                {h.name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
