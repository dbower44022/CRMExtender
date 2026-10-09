/** Mail search box (MAIL-31): operators, Enter to search, Esc to clear,
 * "/" focuses it from anywhere in the mail view, and saved searches kept
 * in this browser (a server-side saved view is deferred; TDD D-36).
 * Helpers live in lib/mailSearchUi.ts.
 */

import { forwardRef, useEffect, useState } from 'react'
import { Bookmark, BookmarkPlus, Search, X } from 'lucide-react'
import { tokenize, type SavedSearch } from '../../lib/mailSearchUi.ts'

const OPERATORS = ['from:', 'to:', 'cc:', 'subject:', 'has:attachment', 'in:', 'label:', 'account:', 'is:unread', 'is:starred', 'before:', 'after:', 'newer_than:7d']

interface Props {
  value: string
  onSearch: (q: string) => void
  saved: SavedSearch[]
  onSaveSearch: (s: SavedSearch) => void
  onRemoveSaved: (name: string) => void
}

export const SearchBox = forwardRef<HTMLInputElement, Props>(function SearchBox(
  { value, onSearch, saved, onSaveSearch, onRemoveSaved }, ref,
) {
  const [draft, setDraft] = useState(value)
  useEffect(() => { setDraft(value) }, [value])
  const [showHelp, setShowHelp] = useState(false)

  const submit = () => onSearch(draft.trim())
  const clear = () => { setDraft(''); onSearch('') }

  return (
    <div className="border-b border-surface-200 bg-surface-0 px-2 py-1.5">
      <div className="flex items-center gap-1 rounded-md border border-surface-300 bg-surface-0 px-2 focus-within:border-primary-400">
        <Search size={14} className="shrink-0 text-surface-400" />
        <input
          ref={ref}
          type="search"
          value={draft}
          placeholder="Search mail  (/)"
          aria-label="Search mail"
          onChange={(e) => setDraft(e.target.value)}
          onFocus={() => setShowHelp(true)}
          onBlur={() => window.setTimeout(() => setShowHelp(false), 150)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') { e.preventDefault(); submit() }
            else if (e.key === 'Escape') { e.preventDefault(); if (draft) clear(); (e.target as HTMLInputElement).blur() }
          }}
          className="min-w-0 flex-1 bg-transparent py-1 text-sm outline-none"
        />
        {draft && (
          <button type="button" onClick={clear} className="text-surface-400 hover:text-surface-700" aria-label="Clear search">
            <X size={14} />
          </button>
        )}
        {value && (
          <button
            type="button"
            title="Save this search"
            aria-label="Save this search"
            className="text-surface-400 hover:text-primary-700"
            onClick={() => {
              const name = window.prompt('Name this search', value)
              if (name) onSaveSearch({ name: name.trim(), query: value })
            }}
          >
            <BookmarkPlus size={14} />
          </button>
        )}
      </div>
      {value && (
        <div className="mt-1 flex flex-wrap gap-1 px-1 text-[11px]">
          {tokenize(value).map((t, i) => (
            <span key={i} className={t.op ? 'rounded bg-primary-50 px-1 text-primary-800' : 'text-surface-500'}>{t.text}</span>
          ))}
        </div>
      )}
      {showHelp && !value && (
        <div className="mt-1 flex flex-wrap gap-1 px-1 text-[11px] text-surface-500">
          {OPERATORS.map((op) => (
            <button
              key={op}
              type="button"
              onMouseDown={(e) => { e.preventDefault(); setDraft((d) => (d ? `${d} ${op}` : op)) }}
              className="rounded bg-surface-100 px-1 hover:bg-surface-200"
            >
              {op}
            </button>
          ))}
        </div>
      )}
      {saved.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-1 px-1 text-[11px]">
          {saved.map((s) => (
            <span key={s.name} className="inline-flex items-center overflow-hidden rounded border border-surface-200">
              <button type="button" onClick={() => onSearch(s.query)} className="inline-flex items-center gap-1 px-1.5 py-0.5 hover:bg-surface-100" title={s.query}>
                <Bookmark size={10} /> {s.name}
              </button>
              <button type="button" onClick={() => onRemoveSaved(s.name)} className="border-l border-surface-200 px-1 text-surface-400 hover:bg-surface-100" aria-label={`Remove saved search ${s.name}`}>
                <X size={10} />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  )
})
