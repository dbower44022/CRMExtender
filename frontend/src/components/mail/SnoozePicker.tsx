/** Snooze picker (MAIL-28): later today, tomorrow, this weekend, next week,
 * or a custom date and time. Opens from the action bar's Snooze button or
 * the `z` key; the choice goes to the outbox as a `snooze` action.
 */

import { useState } from 'react'
import { Clock, X } from 'lucide-react'
import { describeReturn, fromLocalInputValue, snoozeOptions, toLocalInputValue } from '../../lib/snoozeTimes.ts'

interface Props {
  /** How many threads the choice applies to (for the heading). */
  count: number
  onPick: (returnAtIso: string) => void
  onClose: () => void
}

export function SnoozePicker({ count, onPick, onClose }: Props) {
  const now = new Date()
  const options = snoozeOptions(now)
  const [custom, setCustom] = useState(() => toLocalInputValue(new Date(now.getTime() + 60 * 60 * 1000)))
  const customIso = fromLocalInputValue(custom, now)

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/30" onClick={onClose} role="presentation">
      <div
        role="dialog"
        aria-label="Snooze until"
        className="w-[340px] max-w-[92vw] rounded-lg border border-surface-200 bg-surface-0 p-3 shadow-xl"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => { if (e.key === 'Escape') { e.stopPropagation(); onClose() } }}
      >
        <div className="mb-2 flex items-center justify-between">
          <h2 className="flex items-center gap-1.5 text-sm font-semibold text-surface-800">
            <Clock size={14} /> Snooze{count > 1 ? ` ${count} threads` : ''} until
          </h2>
          <button type="button" onClick={onClose} className="rounded p-1 text-surface-500 hover:bg-surface-100" aria-label="Close">
            <X size={16} />
          </button>
        </div>
        <ul className="space-y-1">
          {options.map((o, i) => (
            <li key={o.key}>
              <button
                type="button"
                autoFocus={i === 0}
                onClick={() => onPick(o.at)}
                className="flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-sm text-surface-700 hover:bg-surface-100 focus:bg-surface-100 focus:outline-none"
              >
                <span>{o.label}</span>
                <span className="text-xs text-surface-500">{describeReturn(o.at, now)}</span>
              </button>
            </li>
          ))}
        </ul>
        <div className="mt-2 border-t border-surface-100 pt-2">
          <label className="mb-1 block text-xs font-medium text-surface-600" htmlFor="snooze-custom">Pick a date and time</label>
          <div className="flex items-center gap-2">
            <input
              id="snooze-custom"
              type="datetime-local"
              value={custom}
              min={toLocalInputValue(now)}
              onChange={(e) => setCustom(e.target.value)}
              className="min-w-0 flex-1 rounded border border-surface-300 bg-surface-0 px-2 py-1 text-sm focus:border-primary-400 focus:outline-none"
            />
            <button
              type="button"
              disabled={!customIso}
              onClick={() => customIso && onPick(customIso)}
              className="rounded bg-primary-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-primary-700 disabled:opacity-40"
            >
              Snooze
            </button>
          </div>
          {!customIso && custom && <p className="mt-1 text-xs text-red-600">Choose a time in the future.</p>}
        </div>
      </div>
    </div>
  )
}
