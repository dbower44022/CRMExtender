import { useState } from 'react'
import { Check, ChevronDown, ChevronRight, Loader2, Merge, RotateCcw, X } from 'lucide-react'
import { toast } from 'sonner'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { identity, type MatchCandidate, type MatchSignal } from '../../api/workflows.ts'
import { MergeContactsModal } from '../grid/MergeContactsModal.tsx'

const SIGNAL_LABELS: Record<string, string> = {
  email_exact: 'Same email',
  linkedin_url: 'Same LinkedIn',
  phone_e164: 'Same phone',
  name_exact: 'Same name',
  name_fuzzy: 'Similar name',
  company_exact: 'Same company',
  company_fuzzy: 'Similar company',
  title_match: 'Same title',
  email_domain: 'Same email domain',
}

function signalSummary(signals: MatchSignal[]): string {
  return signals.map((s) => SIGNAL_LABELS[s.name] ?? s.name).join(' · ')
}

export function ReviewQueue() {
  const queryClient = useQueryClient()
  const [sort, setSort] = useState('confidence')
  const [expanded, setExpanded] = useState<string | null>(null)
  const [scanning, setScanning] = useState(false)
  const [merging, setMerging] = useState<MatchCandidate | null>(null)
  const [lastRejected, setLastRejected] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['review-queue', sort],
    queryFn: () => identity.reviewQueue(sort),
  })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['review-queue'] })
    queryClient.invalidateQueries({ queryKey: ['review-count'] })
  }

  const runScan = async () => {
    setScanning(true)
    try {
      const res = await identity.scan()
      toast.success(
        `Scanned ${res.contacts} contacts — ${res.candidates_created} new possible duplicate(s)`)
      refresh()
    } catch {
      toast.error('Scan failed')
    } finally {
      setScanning(false)
    }
  }

  const reject = async (c: MatchCandidate) => {
    try {
      await identity.reject(c.id)
      setLastRejected(c.id)
      refresh()
    } catch {
      toast.error('Could not reject')
    }
  }

  const undoReject = async () => {
    if (!lastRejected) return
    try {
      await identity.restore(lastRejected)
      setLastRejected(null)
      refresh()
    } catch {
      toast.error('Could not undo')
    }
  }

  const candidates = data?.candidates ?? []

  return (
    <div className="h-full overflow-y-auto bg-surface-50 p-6">
      <div className="mx-auto max-w-4xl">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-surface-900">
              Duplicate Review
            </h1>
            <p className="text-sm text-surface-500">
              {data?.pending_count ?? 0} possible duplicate
              {data?.pending_count === 1 ? '' : 's'} to review
            </p>
          </div>
          <div className="flex items-center gap-2">
            <select value={sort} onChange={(e) => setSort(e.target.value)}
              className="rounded-md border border-surface-300 px-2 py-1.5 text-sm">
              <option value="confidence">Sort: Confidence</option>
              <option value="date">Sort: Newest</option>
              <option value="source">Sort: Source</option>
            </select>
            <button onClick={runScan} disabled={scanning}
              className="flex items-center gap-1.5 rounded-md bg-primary-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50">
              {scanning ? <Loader2 size={14} className="animate-spin" /> : <Merge size={14} />}
              Scan for Duplicates
            </button>
          </div>
        </div>

        {lastRejected && (
          <div className="mb-3 flex items-center justify-between rounded-md bg-surface-100 px-3 py-2 text-sm">
            <span className="text-surface-600">Marked as not a match.</span>
            <button onClick={undoReject}
              className="flex items-center gap-1 font-medium text-primary-600 hover:underline">
              <RotateCcw size={12} /> Undo
            </button>
          </div>
        )}

        {isLoading ? (
          <div className="flex items-center gap-2 py-12 text-sm text-surface-400">
            <Loader2 size={16} className="animate-spin" /> Loading…
          </div>
        ) : candidates.length === 0 ? (
          <div className="rounded-lg border border-surface-200 bg-white px-6 py-12 text-center text-sm text-surface-400">
            No duplicates to review. Run a scan to check your contacts.
          </div>
        ) : (
          <ul className="space-y-2">
            {candidates.map((c) => (
              <li key={c.id}
                className="overflow-hidden rounded-lg border border-surface-200 bg-white">
                <div className="flex items-center gap-3 px-4 py-3">
                  <button
                    onClick={() => setExpanded(expanded === c.id ? null : c.id)}
                    className="text-surface-400 hover:text-surface-600">
                    {expanded === c.id
                      ? <ChevronDown size={16} />
                      : <ChevronRight size={16} />}
                  </button>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium text-surface-800">
                      {c.name_a} <span className="text-surface-400">↔</span> {c.name_b}
                    </div>
                    <div className="truncate text-xs text-surface-500">
                      {signalSummary(c.signals)}
                      {c.source && ` · from ${c.source}`}
                    </div>
                  </div>
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
                    c.confidence >= 0.7
                      ? 'bg-amber-100 text-amber-700'
                      : 'bg-surface-100 text-surface-600'
                  }`}>
                    {Math.round(c.confidence * 100)}%
                  </span>
                  <button
                    onClick={() => setMerging(c)}
                    title="Merge these contacts"
                    className="shrink-0 rounded-md bg-green-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-green-700">
                    <Check size={13} className="mr-1 inline" /> Merge
                  </button>
                  <button
                    onClick={() => reject(c)}
                    title="Not a match"
                    className="shrink-0 rounded-md border border-surface-300 px-2.5 py-1 text-xs font-medium text-surface-600 hover:bg-surface-50">
                    <X size={13} className="mr-1 inline" /> Not a match
                  </button>
                </div>

                {expanded === c.id && (
                  <div className="border-t border-surface-100 bg-surface-50 px-4 py-3">
                    <div className="grid grid-cols-2 gap-3">
                      {[
                        { name: c.name_a, email: c.email_a },
                        { name: c.name_b, email: c.email_b },
                      ].map((p, i) => (
                        <div key={i} className="rounded-md border border-surface-200 bg-white p-3">
                          <div className="text-sm font-medium text-surface-800">{p.name}</div>
                          <div className="text-xs text-surface-500">{p.email || 'no email'}</div>
                        </div>
                      ))}
                    </div>
                    <div className="mt-2">
                      <div className="mb-1 text-xs font-semibold uppercase text-surface-500">
                        Matching signals
                      </div>
                      <ul className="space-y-0.5">
                        {c.signals.map((s, i) => (
                          <li key={i} className="flex items-center justify-between text-xs">
                            <span className="text-surface-600">
                              {SIGNAL_LABELS[s.name] ?? s.name}
                              {s.value_a && s.value_a === s.value_b && (
                                <span className="ml-1 text-surface-400">({s.value_a})</span>
                              )}
                            </span>
                            <span className="tabular-nums text-surface-400">
                              +{Math.round(s.weight * 100)}%
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      {merging && (
        <MergeContactsModal
          contactIds={[merging.contact_a_id, merging.contact_b_id]}
          onClose={() => { setMerging(null); refresh() }}
        />
      )}
    </div>
  )
}
