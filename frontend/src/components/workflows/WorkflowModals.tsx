/** Phase 4 workflow modals: create event/project, vCard import,
 * bulk-assign communications, company duplicates report, add relationship.
 * One shared modal shell keeps them compact. */

import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Loader2, X } from 'lucide-react'
import { toast } from 'sonner'
import { useQueryClient } from '@tanstack/react-query'
import { workflows, type RelationshipTypeRow } from '../../api/workflows.ts'
import { get } from '../../api/client.ts'
import { useNavigationStore } from '../../stores/navigation.ts'

function Modal({ title, onClose, children, wide = false }: {
  title: string
  onClose: () => void
  children: React.ReactNode
  wide?: boolean
}) {
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
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className={`relative mx-4 flex max-h-[85vh] w-full flex-col rounded-lg bg-white shadow-xl ${wide ? 'max-w-2xl' : 'max-w-md'}`}>
        <div className="flex items-center justify-between border-b border-surface-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-surface-900">{title}</h2>
          <button onClick={onClose}
            className="rounded-md p-1 text-surface-400 hover:bg-surface-100 hover:text-surface-600">
            <X size={20} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-4">{children}</div>
      </div>
    </div>,
    document.body,
  )
}

const inputCls =
  'w-full rounded-md border border-surface-300 bg-surface-0 px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-200'
const labelCls = 'mb-1 block text-sm font-medium text-surface-700'
const primaryBtn =
  'rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-700 disabled:opacity-50'

/* ------------------------------------------------------------------ */

export function AddEventModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState({
    title: '', event_type: 'meeting', start_datetime: '', end_datetime: '',
    is_all_day: false, location: '', description: '', status: 'confirmed',
  })
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!form.title.trim()) {
      toast.error('Title is required')
      return
    }
    setSaving(true)
    try {
      await workflows.createEvent({
        ...form,
        title: form.title.trim(),
        // datetime-local gives "YYYY-MM-DDTHH:MM" — store as-is
      })
      toast.success('Event created')
      queryClient.invalidateQueries({ queryKey: ['view-data'] })
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Create failed')
    } finally {
      setSaving(false)
    }
  }

  const f = (k: keyof typeof form) => ({
    value: String(form[k] ?? ''),
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
      setForm({ ...form, [k]: e.target.value }),
  })

  return (
    <Modal title="Add Event" onClose={onClose}>
      <div className="space-y-3">
        <div>
          <label className={labelCls}>Title <span className="text-red-500">*</span></label>
          <input className={inputCls} {...f('title')} autoFocus />
        </div>
        <div className="flex gap-2">
          <div className="flex-1">
            <label className={labelCls}>Type</label>
            <select className={inputCls} {...f('event_type')}>
              {['meeting', 'birthday', 'anniversary', 'conference', 'deadline', 'other']
                .map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div className="flex-1">
            <label className={labelCls}>Status</label>
            <select className={inputCls} {...f('status')}>
              {['confirmed', 'tentative', 'cancelled']
                .map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        </div>
        <div className="flex gap-2">
          <div className="flex-1">
            <label className={labelCls}>Starts</label>
            <input type="datetime-local" className={inputCls} {...f('start_datetime')} />
          </div>
          <div className="flex-1">
            <label className={labelCls}>Ends</label>
            <input type="datetime-local" className={inputCls} {...f('end_datetime')} />
          </div>
        </div>
        <label className="flex items-center gap-2 text-sm text-surface-700">
          <input type="checkbox" checked={form.is_all_day}
            onChange={(e) => setForm({ ...form, is_all_day: e.target.checked })} />
          All day
        </label>
        <div>
          <label className={labelCls}>Location</label>
          <input className={inputCls} {...f('location')} />
        </div>
        <div>
          <label className={labelCls}>Description</label>
          <textarea className={inputCls} rows={3} {...f('description')} />
        </div>
        <button onClick={submit} disabled={saving} className={primaryBtn}>
          {saving ? 'Creating…' : 'Create Event'}
        </button>
      </div>
    </Modal>
  )
}

/* ------------------------------------------------------------------ */

export function AddProjectModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!name.trim()) {
      toast.error('Name is required')
      return
    }
    setSaving(true)
    try {
      await workflows.createProject(name.trim(), description.trim())
      toast.success('Project created')
      queryClient.invalidateQueries({ queryKey: ['view-data'] })
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Create failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title="Add Project" onClose={onClose}>
      <div className="space-y-3">
        <div>
          <label className={labelCls}>Name <span className="text-red-500">*</span></label>
          <input className={inputCls} value={name}
            onChange={(e) => setName(e.target.value)} autoFocus />
        </div>
        <div>
          <label className={labelCls}>Description</label>
          <textarea className={inputCls} rows={3} value={description}
            onChange={(e) => setDescription(e.target.value)} />
        </div>
        <button onClick={submit} disabled={saving} className={primaryBtn}>
          {saving ? 'Creating…' : 'Create Project'}
        </button>
      </div>
    </Modal>
  )
}

/* ------------------------------------------------------------------ */

export function ImportVcardsModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient()
  const [path, setPath] = useState('')
  const [recursive, setRecursive] = useState(false)
  const [running, setRunning] = useState(false)
  const [report, setReport] = useState<Record<string, unknown> | null>(null)

  const submit = async () => {
    if (!path.trim()) {
      toast.error('Path is required')
      return
    }
    setRunning(true)
    try {
      const result = await workflows.importVcards(path.trim(), recursive)
      setReport(result)
      queryClient.invalidateQueries({ queryKey: ['view-data'] })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Import failed')
    } finally {
      setRunning(false)
    }
  }

  return (
    <Modal title="Import vCards" onClose={onClose} wide>
      {report ? (
        <div className="space-y-2 text-sm">
          <div className="grid grid-cols-2 gap-2">
            {[
              ['Files processed', 'files_processed'],
              ['vCards parsed', 'vcards_parsed'],
              ['Contacts created', 'contacts_created'],
              ['Duplicates skipped', 'contacts_skipped_duplicate'],
              ['Companies created', 'companies_created'],
              ['Phones added', 'phones_added'],
            ].map(([label, key]) => (
              <div key={key} className="rounded-md border border-surface-200 p-2">
                <div className="text-xs text-surface-500">{label}</div>
                <div className="text-lg font-semibold tabular-nums">
                  {Number(report[key] ?? 0)}
                </div>
              </div>
            ))}
          </div>
          {Array.isArray(report.errors) && report.errors.length > 0 && (
            <div className="rounded-md bg-red-50 p-2 text-xs text-red-700">
              {(report.errors as string[]).slice(0, 5).map((e, i) => (
                <div key={i}>{e}</div>
              ))}
            </div>
          )}
          <button onClick={onClose} className={primaryBtn}>Done</button>
        </div>
      ) : (
        <div className="space-y-3">
          <div>
            <label className={labelCls}>
              Server path to a .vcf file or directory
            </label>
            <input className={inputCls} value={path} autoFocus
              placeholder="/home/you/contacts.vcf"
              onChange={(e) => setPath(e.target.value)} />
          </div>
          <label className="flex items-center gap-2 text-sm text-surface-700">
            <input type="checkbox" checked={recursive}
              onChange={(e) => setRecursive(e.target.checked)} />
            Search subdirectories
          </label>
          <button onClick={submit} disabled={running} className={primaryBtn}>
            {running ? (
              <span className="flex items-center gap-2">
                <Loader2 size={13} className="animate-spin" /> Importing…
              </span>
            ) : 'Import'}
          </button>
        </div>
      )}
    </Modal>
  )
}

/* ------------------------------------------------------------------ */

export function AssignCommunicationsModal({ ids, onClose }: {
  ids: string[]
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const [q, setQ] = useState('')
  const [targets, setTargets] = useState<
    { id: string; title: string }[] | null>(null)

  useEffect(() => {
    const t = setTimeout(async () => {
      try {
        const res = await workflows.assignTargets(q)
        setTargets(res.conversations)
      } catch {
        setTargets([])
      }
    }, 250)
    return () => clearTimeout(t)
  }, [q])

  const assign = async (conversationId: string) => {
    try {
      const res = await workflows.assignCommunications(ids, conversationId)
      toast.success(
        `${res.assigned} assigned${res.skipped_existing ? `, ${res.skipped_existing} already linked` : ''}`)
      queryClient.invalidateQueries({ queryKey: ['view-data'] })
      useNavigationStore.getState().deselectAllRows()
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Assign failed')
    }
  }

  return (
    <Modal title={`Assign ${ids.length} communication${ids.length === 1 ? '' : 's'}`} onClose={onClose}>
      <input className={inputCls} value={q} autoFocus
        placeholder="Search conversations…"
        onChange={(e) => setQ(e.target.value)} />
      <ul className="mt-2 max-h-64 divide-y divide-surface-100 overflow-y-auto rounded-md border border-surface-200">
        {targets === null ? (
          <li className="px-3 py-2 text-sm text-surface-400">Loading…</li>
        ) : targets.length === 0 ? (
          <li className="px-3 py-2 text-sm text-surface-400">No conversations found</li>
        ) : targets.map((t) => (
          <li key={t.id}>
            <button onClick={() => assign(t.id)}
              className="w-full px-3 py-2 text-left text-sm hover:bg-surface-50">
              {t.title || 'Untitled'}
            </button>
          </li>
        ))}
      </ul>
    </Modal>
  )
}

/* ------------------------------------------------------------------ */

export function CompanyDuplicatesModal({ onClose }: { onClose: () => void }) {
  const [groups, setGroups] = useState<
    { domain: string; companies: { id: string; name: string }[] }[] | null>(null)

  useEffect(() => {
    workflows.companyDuplicates()
      .then((res) => setGroups(res.groups))
      .catch(() => setGroups([]))
  }, [])

  const open = (id: string) => {
    const nav = useNavigationStore.getState()
    nav.setActiveEntityType('company')
    nav.setPendingNavigation({ entityType: 'company', entityId: id })
    onClose()
  }

  return (
    <Modal title="Possible Duplicate Companies" onClose={onClose} wide>
      {groups === null ? (
        <div className="text-sm text-surface-400">Scanning…</div>
      ) : groups.length === 0 ? (
        <div className="text-sm text-surface-400">
          No duplicate companies detected.
        </div>
      ) : (
        <div className="space-y-3">
          {groups.map((g) => (
            <div key={g.domain} className="rounded-md border border-surface-200">
              <div className="border-b border-surface-100 bg-surface-50 px-3 py-1.5 text-xs font-semibold text-surface-600">
                {g.domain}
              </div>
              <ul className="divide-y divide-surface-100">
                {g.companies.map((c) => (
                  <li key={c.id}>
                    <button onClick={() => open(c.id)}
                      className="w-full px-3 py-1.5 text-left text-sm text-primary-600 hover:bg-surface-50">
                      {c.name}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
          <p className="text-xs text-surface-400">
            Use “Merge Duplicates” in the companies grid after selecting the
            rows to combine.
          </p>
        </div>
      )}
    </Modal>
  )
}

/* ------------------------------------------------------------------ */

interface PickerHit { id: string; name: string }

function EntityPicker({ entityType, value, onChange }: {
  entityType: 'contact' | 'company'
  value: PickerHit | null
  onChange: (v: PickerHit | null) => void
}) {
  const [q, setQ] = useState('')
  const [hits, setHits] = useState<PickerHit[]>([])

  useEffect(() => {
    const t = setTimeout(async () => {
      if (q.length < 2) {
        setHits([])
        return
      }
      try {
        const res = await get<{
          groups: { entity_type: string; results: { id: string; name: string }[] }[]
        }>(`/search?q=${encodeURIComponent(q)}&entity_type=${entityType}&limit=8`)
        const group = res.groups.find((g) => g.entity_type === entityType)
        setHits((group?.results ?? []).map((r) => ({ id: r.id, name: r.name })))
      } catch {
        setHits([])
      }
    }, 250)
    return () => clearTimeout(t)
  }, [q, entityType])

  if (value) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-surface-200 bg-surface-50 px-2 py-1.5 text-sm">
        <span className="flex-1 truncate">{value.name}</span>
        <button onClick={() => onChange(null)}
          className="text-surface-400 hover:text-surface-600"><X size={13} /></button>
      </div>
    )
  }
  return (
    <div className="relative">
      <input className={inputCls} value={q}
        placeholder={`Search ${entityType === 'contact' ? 'contacts' : 'companies'}…`}
        onChange={(e) => setQ(e.target.value)} />
      {hits.length > 0 && (
        <ul className="absolute z-10 mt-1 max-h-40 w-full overflow-y-auto rounded-md border border-surface-200 bg-white shadow-lg">
          {hits.map((h) => (
            <li key={h.id}>
              <button onClick={() => { onChange(h); setQ('') }}
                className="w-full px-3 py-1.5 text-left text-sm hover:bg-surface-50">
                {h.name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function AddRelationshipModal({ onClose, fromIds }: {
  onClose: () => void
  /** Preselected "from" contact ids (grid selection); empty → pick one */
  fromIds: string[]
}) {
  const queryClient = useQueryClient()
  const [types, setTypes] = useState<RelationshipTypeRow[]>([])
  const [typeId, setTypeId] = useState('')
  const [fromPick, setFromPick] = useState<PickerHit | null>(null)
  const [toPick, setToPick] = useState<PickerHit | null>(null)
  const [saving, setSaving] = useState(false)

  const selectedType = types.find((t) => t.id === typeId)
  const toType = (selectedType?.to_entity_type ?? 'contact') as 'contact' | 'company'

  useEffect(() => {
    workflows.relationshipTypes('contact')
      .then((res) => {
        setTypes(res.types)
        if (res.types[0]) setTypeId(res.types[0].id)
      })
      .catch(() => toast.error('Could not load relationship types'))
  }, [])

  const submit = async () => {
    const from = fromIds.length ? fromIds : fromPick ? [fromPick.id] : []
    if (!typeId || !from.length || !toPick) {
      toast.error('Pick a type, source and target')
      return
    }
    setSaving(true)
    try {
      const res = await workflows.createRelationships({
        relationship_type_id: typeId,
        to_entity_id: toPick.id,
        from_entity_ids: from,
      })
      const skipped = res.results.filter((r) => r.status !== 'created').length
      toast.success(
        `${res.created} relationship${res.created === 1 ? '' : 's'} created${skipped ? `, ${skipped} skipped` : ''}`)
      queryClient.invalidateQueries({ queryKey: ['view-data'] })
      useNavigationStore.getState().deselectAllRows()
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Create failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title="Add Relationship" onClose={onClose}>
      <div className="space-y-3">
        {fromIds.length > 0 ? (
          <div className="text-sm text-surface-600">
            From: {fromIds.length} selected contact{fromIds.length === 1 ? '' : 's'}
          </div>
        ) : (
          <div>
            <label className={labelCls}>From contact</label>
            <EntityPicker entityType="contact" value={fromPick} onChange={setFromPick} />
          </div>
        )}
        <div>
          <label className={labelCls}>Relationship type</label>
          <select className={inputCls} value={typeId}
            onChange={(e) => setTypeId(e.target.value)}>
            {types.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} ({t.forward_label || t.name} → {t.to_entity_type})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelCls}>
            Target {toType === 'contact' ? 'contact' : 'company'}
          </label>
          <EntityPicker entityType={toType} value={toPick} onChange={setToPick} />
        </div>
        <button onClick={submit} disabled={saving} className={primaryBtn}>
          {saving ? 'Creating…' : 'Create'}
        </button>
      </div>
    </Modal>
  )
}
