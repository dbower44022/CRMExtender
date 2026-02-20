import { useRef, useCallback, useEffect, useState } from 'react'
import { Search, X } from 'lucide-react'
import { useNavigationStore } from '../../stores/navigation.ts'

export function GridToolbar() {
  const search = useNavigationStore((s) => s.search)
  const setSearch = useNavigationStore((s) => s.setSearch)
  const [localSearch, setLocalSearch] = useState(search)
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined)
  const inputRef = useRef<HTMLInputElement>(null)

  const debouncedSearch = useCallback(
    (value: string) => {
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => setSearch(value), 300)
    },
    [setSearch],
  )

  useEffect(() => {
    setLocalSearch(search)
  }, [search])

  const handleChange = (value: string) => {
    setLocalSearch(value)
    debouncedSearch(value)
  }

  const handleClear = () => {
    setLocalSearch('')
    setSearch('')
    inputRef.current?.focus()
  }

  return (
    <div className="flex items-center gap-3 border-b border-surface-200 px-4 py-2">
      <div className="relative flex-1 max-w-sm">
        <Search
          size={14}
          className="absolute left-2.5 top-1/2 -translate-y-1/2 text-surface-400"
        />
        <input
          ref={inputRef}
          type="text"
          value={localSearch}
          onChange={(e) => handleChange(e.target.value)}
          placeholder="Quick filter..."
          className="h-8 w-full rounded-md border border-surface-200 bg-surface-0 pl-8 pr-8 text-sm text-surface-700 outline-none transition-colors placeholder:text-surface-400 focus:border-primary-300 focus:ring-1 focus:ring-primary-200"
        />
        {localSearch && (
          <button
            onClick={handleClear}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-surface-400 hover:text-surface-600"
          >
            <X size={14} />
          </button>
        )}
      </div>
    </div>
  )
}
