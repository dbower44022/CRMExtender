/** The keyboard shortcut sheet (MAIL-30), opened with "?". */

import { X } from 'lucide-react'
import { SHORTCUT_ROWS } from '../../hooks/useMailShortcuts.ts'

export function ShortcutSheet({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/30" onClick={onClose} role="presentation">
      <div
        role="dialog"
        aria-label="Keyboard shortcuts"
        className="max-h-[80vh] w-[520px] max-w-[92vw] overflow-y-auto rounded-lg border border-surface-200 bg-surface-0 p-4 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-surface-800">Mail keyboard shortcuts</h2>
          <button type="button" onClick={onClose} className="rounded p-1 text-surface-500 hover:bg-surface-100" aria-label="Close">
            <X size={16} />
          </button>
        </div>
        <table className="w-full text-sm">
          <tbody>
            {SHORTCUT_ROWS.map((r) => (
              <tr key={r.keys} className="border-t border-surface-100">
                <td className="whitespace-nowrap py-1.5 pr-4 font-mono text-xs text-surface-700">{r.keys}</td>
                <td className="py-1.5 text-surface-700">
                  {r.action}
                  {r.note && <span className="ml-2 rounded bg-surface-100 px-1 text-[10px] text-surface-500">coming with {r.note}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
