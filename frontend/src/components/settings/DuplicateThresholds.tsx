import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { get, put } from '../../api/client.ts'

interface Thresholds {
  auto: number
  flag: number
  review: number
}

const ROWS: { key: keyof Thresholds; label: string; help: string }[] = [
  { key: 'auto', label: 'Auto-merge', help: 'Confidence at or above this is treated as the same person.' },
  { key: 'flag', label: 'Flag for review', help: 'High-confidence matches surface prominently.' },
  { key: 'review', label: 'Queue for review', help: 'The minimum confidence that creates a review-queue candidate.' },
]

/** Tenant-configurable duplicate-detection thresholds (IDENT-10). */
export function DuplicateThresholds() {
  const [thresholds, setThresholds] = useState<Thresholds | null>(null)
  const [defaults, setDefaults] = useState<Thresholds | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    get<{ thresholds: Thresholds; defaults: Thresholds }>(
      '/settings/duplicate-thresholds')
      .then((r) => { setThresholds(r.thresholds); setDefaults(r.defaults) })
      .catch(() => toast.error('Could not load duplicate settings'))
  }, [])

  const save = async () => {
    if (!thresholds) return
    setSaving(true)
    try {
      await put('/settings/duplicate-thresholds', thresholds)
      toast.success('Duplicate thresholds saved')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  if (!thresholds) return null

  return (
    <div className="mt-8 border-t border-surface-200 pt-6">
      <h2 className="mb-1 text-base font-semibold text-surface-800">
        Duplicate Detection
      </h2>
      <p className="mb-4 text-sm text-surface-500">
        Confidence thresholds that decide when two contacts are flagged as
        possible duplicates. Changes apply to future scans and new contacts.
      </p>
      <div className="space-y-4">
        {ROWS.map(({ key, label, help }) => (
          <div key={key}>
            <div className="mb-1 flex items-center justify-between">
              <label className="text-sm font-medium text-surface-700">
                {label}
              </label>
              <span className="text-sm tabular-nums text-surface-600">
                {Math.round(thresholds[key] * 100)}%
                {defaults && thresholds[key] !== defaults[key] && (
                  <span className="ml-1 text-xs text-surface-400">
                    (default {Math.round(defaults[key] * 100)}%)
                  </span>
                )}
              </span>
            </div>
            <input
              type="range" min={0} max={1} step={0.05}
              value={thresholds[key]}
              onChange={(e) => setThresholds({
                ...thresholds, [key]: Number(e.target.value),
              })}
              className="w-full"
            />
            <p className="mt-0.5 text-xs text-surface-400">{help}</p>
          </div>
        ))}
      </div>
      <button
        onClick={save}
        disabled={saving}
        className="mt-4 rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-700 disabled:opacity-50"
      >
        {saving ? 'Saving…' : 'Save Thresholds'}
      </button>
    </div>
  )
}
