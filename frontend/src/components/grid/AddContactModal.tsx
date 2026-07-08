import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { AlertTriangle, X } from 'lucide-react'
import { toast } from 'sonner'
import { post } from '../../api/client.ts'
import { useCreateContact } from '../../api/contacts.ts'
import { useNavigationStore } from '../../stores/navigation.ts'
import { useLayoutStore } from '../../stores/layout.ts'

interface AddContactModalProps {
  onClose: () => void
}

interface DuplicateMatch {
  id: string
  name: string
  email: string | null
  match_on: string[]
}

interface CompanyHit {
  id: string
  name: string
}

const inputCls =
  'w-full rounded-md border border-surface-300 bg-surface-0 px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-200'
const labelCls = 'mb-1 block text-sm font-medium text-surface-700'

/** Contact creation per Contact Entity Base PRD KP-1: full field set,
 * inline duplicate detection, and landing on the new record. */
export function AddContactModal({ onClose }: AddContactModalProps) {
  const create = useCreateContact()

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [title, setTitle] = useState('')
  const [socialUrl, setSocialUrl] = useState('')
  const [company, setCompany] = useState<CompanyHit | null>(null)
  const [companyQuery, setCompanyQuery] = useState('')
  const [companyHits, setCompanyHits] = useState<CompanyHit[]>([])
  const [duplicates, setDuplicates] = useState<DuplicateMatch[]>([])
  const [error, setError] = useState('')

  // Inline duplicate detection (KP-1 step 2), debounced on the
  // identifying fields
  useEffect(() => {
    const t = setTimeout(async () => {
      if (!name.trim() && !email.trim() && !phone.trim()) {
        setDuplicates([])
        return
      }
      try {
        const res = await post<{ matches: DuplicateMatch[] }>(
          '/contacts/check',
          { name: name.trim(), email: email.trim(), phone: phone.trim() },
        )
        setDuplicates(res.matches)
      } catch {
        setDuplicates([])
      }
    }, 350)
    return () => clearTimeout(t)
  }, [name, email, phone])

  // Company picker search
  useEffect(() => {
    const t = setTimeout(async () => {
      if (companyQuery.length < 2) {
        setCompanyHits([])
        return
      }
      try {
        const res = await fetch(
          `/api/v1/search?q=${encodeURIComponent(companyQuery)}&entity_type=company&limit=6`,
        ).then((r) => r.json())
        const group = res.groups?.find(
          (g: { entity_type: string }) => g.entity_type === 'company')
        setCompanyHits(
          (group?.results ?? []).map(
            (r: { id: string; name: string }) => ({ id: r.id, name: r.name })))
      } catch {
        setCompanyHits([])
      }
    }, 250)
    return () => clearTimeout(t)
  }, [companyQuery])

  const openExisting = (contactId: string) => {
    const nav = useNavigationStore.getState()
    nav.setActiveEntityType('contact')
    nav.setPendingNavigation({ entityType: 'contact', entityId: contactId })
    onClose()
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (!name.trim()) {
      setError('Name is required')
      return
    }
    create.mutate(
      {
        name: name.trim(),
        email: email.trim() || undefined,
        phone: phone.trim() || undefined,
        company_id: company?.id,
        title: title.trim() || undefined,
        social_url: socialUrl.trim() || undefined,
        source: 'manual',
      },
      {
        onSuccess: (result) => {
          toast.success(`Contact "${result.name}" created`)
          // Land on the new record (KP-1 step 4)
          const nav = useNavigationStore.getState()
          nav.setPendingNavigation({
            entityType: 'contact',
            entityId: String(result.id),
          })
          useLayoutStore.getState().showDetailPanel()
          onClose()
        },
        onError: (err) => {
          setError(err.message || 'Failed to create contact')
        },
      },
    )
  }

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
      <div className="relative mx-4 flex max-h-[90vh] w-full max-w-md flex-col rounded-lg bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-surface-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-surface-900">Add Contact</h2>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-surface-400 hover:bg-surface-100 hover:text-surface-600"
          >
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto px-6 py-4">
          {error && (
            <div className="mb-4 rounded-md bg-red-50 px-4 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          {duplicates.length > 0 && (
            <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2">
              <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-amber-700">
                <AlertTriangle size={12} />
                Possible duplicate{duplicates.length === 1 ? '' : 's'}
              </div>
              {duplicates.slice(0, 3).map((d) => (
                <div key={d.id} className="flex items-center gap-2 py-0.5 text-xs">
                  <span className="min-w-0 flex-1 truncate text-amber-800">
                    {d.name}
                    {d.email && ` · ${d.email}`}
                    <span className="text-amber-500"> (matches {d.match_on.join(', ')})</span>
                  </span>
                  <button
                    type="button"
                    onClick={() => openExisting(d.id)}
                    className="shrink-0 font-medium text-amber-700 underline"
                  >
                    Open
                  </button>
                </div>
              ))}
              <div className="mt-1 text-xs text-amber-600">
                You can still create a new contact below.
              </div>
            </div>
          )}

          <div className="space-y-3">
            <div>
              <label className={labelCls}>
                Name <span className="text-red-500">*</span>
              </label>
              <input className={inputCls} value={name} autoFocus
                onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="flex gap-2">
              <div className="flex-1">
                <label className={labelCls}>Email</label>
                <input className={inputCls} type="email" value={email}
                  onChange={(e) => setEmail(e.target.value)} />
              </div>
              <div className="flex-1">
                <label className={labelCls}>Phone</label>
                <input className={inputCls} value={phone}
                  placeholder="(330) 555-0100"
                  onChange={(e) => setPhone(e.target.value)} />
              </div>
            </div>
            <div>
              <label className={labelCls}>Company</label>
              {company ? (
                <div className="flex items-center gap-2 rounded-md border border-surface-200 bg-surface-50 px-3 py-2 text-sm">
                  <span className="flex-1 truncate">{company.name}</span>
                  <button type="button" onClick={() => setCompany(null)}
                    className="text-surface-400 hover:text-surface-600">
                    <X size={13} />
                  </button>
                </div>
              ) : (
                <div className="relative">
                  <input className={inputCls} value={companyQuery}
                    placeholder="Search companies…"
                    onChange={(e) => setCompanyQuery(e.target.value)} />
                  {companyHits.length > 0 && (
                    <ul className="absolute z-10 mt-1 max-h-36 w-full overflow-y-auto rounded-md border border-surface-200 bg-white shadow-lg">
                      {companyHits.map((h) => (
                        <li key={h.id}>
                          <button type="button"
                            onClick={() => { setCompany(h); setCompanyQuery('') }}
                            className="w-full px-3 py-1.5 text-left text-sm hover:bg-surface-50">
                            {h.name}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
            {company && (
              <div>
                <label className={labelCls}>Job Title</label>
                <input className={inputCls} value={title}
                  onChange={(e) => setTitle(e.target.value)} />
              </div>
            )}
            <div>
              <label className={labelCls}>LinkedIn / social URL</label>
              <input className={inputCls} value={socialUrl}
                placeholder="https://linkedin.com/in/…"
                onChange={(e) => setSocialUrl(e.target.value)} />
            </div>
          </div>

          <div className="mt-5 flex justify-end gap-2">
            <button type="button" onClick={onClose}
              className="rounded-md px-4 py-2 text-sm text-surface-600 hover:bg-surface-100">
              Cancel
            </button>
            <button type="submit" disabled={create.isPending}
              className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50">
              {create.isPending ? 'Creating…' : 'Create Contact'}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body,
  )
}
