import { useEffect, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { workflows, type RelationshipTypeRow } from '../../api/workflows.ts'

const inputCls =
  'w-full rounded-md border border-surface-300 bg-surface-0 px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-200'

export function RelationshipTypesSettings() {
  const [types, setTypes] = useState<RelationshipTypeRow[] | null>(null)
  const [adding, setAdding] = useState(false)
  const [confirming, setConfirming] = useState<string | null>(null)
  const [form, setForm] = useState({
    name: '', from_entity_type: 'contact', to_entity_type: 'contact',
    forward_label: '', reverse_label: '', is_bidirectional: false,
  })

  const load = () =>
    workflows.relationshipTypes()
      .then((res) => setTypes(res.types))
      .catch(() => toast.error('Could not load relationship types'))

  useEffect(() => {
    load()
  }, [])

  const submit = async () => {
    if (!form.name.trim()) {
      toast.error('Name is required')
      return
    }
    try {
      await workflows.createRelationshipType({ ...form, name: form.name.trim() })
      toast.success('Relationship type created')
      setAdding(false)
      setForm({ name: '', from_entity_type: 'contact', to_entity_type: 'contact',
                forward_label: '', reverse_label: '', is_bidirectional: false })
      load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Create failed')
    }
  }

  const remove = async (typeId: string) => {
    if (confirming !== typeId) {
      setConfirming(typeId)
      return
    }
    setConfirming(null)
    try {
      await workflows.deleteRelationshipType(typeId)
      toast.success('Relationship type deleted')
      load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Delete failed')
    }
  }

  return (
    <div className="mx-auto w-full max-w-2xl">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-surface-800">Relationship Types</h1>
        <button onClick={() => setAdding(!adding)}
          className="flex items-center gap-1.5 rounded-md bg-primary-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-700">
          <Plus size={14} /> New Type
        </button>
      </div>

      {adding && (
        <div className="mb-4 space-y-3 rounded-lg border border-surface-200 p-4">
          <input className={inputCls} placeholder="Name (e.g. Mentor)" autoFocus
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <div className="flex gap-2">
            <select className={inputCls} value={form.from_entity_type}
              onChange={(e) => setForm({ ...form, from_entity_type: e.target.value })}>
              <option value="contact">From: Contact</option>
              <option value="company">From: Company</option>
            </select>
            <select className={inputCls} value={form.to_entity_type}
              onChange={(e) => setForm({ ...form, to_entity_type: e.target.value })}>
              <option value="contact">To: Contact</option>
              <option value="company">To: Company</option>
            </select>
          </div>
          <div className="flex gap-2">
            <input className={inputCls} placeholder="Forward label (e.g. Mentors)"
              value={form.forward_label}
              onChange={(e) => setForm({ ...form, forward_label: e.target.value })} />
            <input className={inputCls} placeholder="Reverse label (e.g. Mentored by)"
              value={form.reverse_label}
              onChange={(e) => setForm({ ...form, reverse_label: e.target.value })} />
          </div>
          <label className="flex items-center gap-2 text-sm text-surface-700">
            <input type="checkbox" checked={form.is_bidirectional}
              onChange={(e) => setForm({ ...form, is_bidirectional: e.target.checked })} />
            Bidirectional (creates both directions)
          </label>
          <button onClick={submit}
            className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700">
            Create
          </button>
        </div>
      )}

      {types === null ? (
        <div className="text-sm text-surface-500">Loading…</div>
      ) : (
        <ul className="divide-y divide-surface-100 rounded-lg border border-surface-200">
          {types.map((t) => (
            <li key={t.id} className="flex items-center gap-3 px-4 py-2.5">
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-surface-800">{t.name}</div>
                <div className="text-xs text-surface-400">
                  {t.from_entity_type} → {t.to_entity_type}
                  {t.forward_label && ` · ${t.forward_label}`}
                  {t.reverse_label && ` / ${t.reverse_label}`}
                  {!!t.is_bidirectional && ' · bidirectional'}
                </div>
              </div>
              {t.is_system ? (
                <span className="shrink-0 rounded bg-surface-100 px-2 py-0.5 text-xs text-surface-500">
                  system
                </span>
              ) : confirming === t.id ? (
                <button onClick={() => remove(t.id)} onBlur={() => setConfirming(null)}
                  className="shrink-0 rounded bg-red-600 px-2 py-0.5 text-xs font-medium text-white">
                  Confirm
                </button>
              ) : (
                <button onClick={() => remove(t.id)} title="Delete"
                  className="shrink-0 rounded p-1 text-surface-300 hover:bg-red-50 hover:text-red-600">
                  <Trash2 size={13} />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
