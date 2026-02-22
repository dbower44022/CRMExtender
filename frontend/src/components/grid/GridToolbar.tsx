import { useRef, useCallback, useEffect, useState } from 'react'
import { Search, X, Columns3, Filter, Minimize2 } from 'lucide-react'
import { useNavigationStore } from '../../stores/navigation.ts'
import { useViewConfig } from '../../api/views.ts'
import { useGridIntelligenceStore } from '../../stores/gridIntelligence.ts'
import { ColumnPicker } from './ColumnPicker.tsx'
import { FilterBuilder } from './FilterBuilder.tsx'
import { QuickFilters } from './QuickFilters.tsx'

export function GridToolbar() {
  const search = useNavigationStore((s) => s.search)
  const setSearch = useNavigationStore((s) => s.setSearch)
  const activeViewId = useNavigationStore((s) => s.activeViewId)
  const { data: viewConfig } = useViewConfig(activeViewId)
  const computedLayout = useGridIntelligenceStore((s) => s.computedLayout)
  const [localSearch, setLocalSearch] = useState(search)
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined)
  const inputRef = useRef<HTMLInputElement>(null)

  const [showColumns, setShowColumns] = useState(false)
  const [showFilters, setShowFilters] = useState(false)

  const filterCount = viewConfig?.filters?.length ?? 0
  const demotedCount = (computedLayout?.demotedCount ?? 0) + (computedLayout?.hiddenCount ?? 0)

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
    <div className="border-b border-surface-200 px-4 py-2">
      <div className="flex items-center gap-2">
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
            placeholder="Search..."
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

        {/* Columns button */}
        <div className="relative">
          <button
            onClick={() => {
              setShowColumns(!showColumns)
              setShowFilters(false)
            }}
            className={`flex h-8 items-center gap-1.5 rounded-md border px-2.5 text-xs font-medium transition-colors ${
              showColumns
                ? 'border-primary-300 bg-primary-50 text-primary-700'
                : 'border-surface-200 bg-surface-0 text-surface-600 hover:bg-surface-50'
            }`}
          >
            <Columns3 size={14} />
            Columns
          </button>
          {showColumns && <ColumnPicker onClose={() => setShowColumns(false)} />}
        </div>

        {/* Filter button */}
        <div className="relative">
          <button
            onClick={() => {
              setShowFilters(!showFilters)
              setShowColumns(false)
            }}
            className={`flex h-8 items-center gap-1.5 rounded-md border px-2.5 text-xs font-medium transition-colors ${
              showFilters || filterCount > 0
                ? 'border-primary-300 bg-primary-50 text-primary-700'
                : 'border-surface-200 bg-surface-0 text-surface-600 hover:bg-surface-50'
            }`}
          >
            <Filter size={14} />
            Filter
            {filterCount > 0 && (
              <span className="flex h-4 min-w-[16px] items-center justify-center rounded-full bg-primary-600 px-1 text-[10px] font-semibold text-white">
                {filterCount}
              </span>
            )}
          </button>
          {showFilters && (
            <FilterBuilder onClose={() => setShowFilters(false)} />
          )}
        </div>

        {/* Demoted columns indicator */}
        {demotedCount > 0 && (
          <div className="flex h-8 items-center gap-1.5 rounded-md border border-surface-200 bg-surface-0 px-2.5 text-xs text-surface-500">
            <Minimize2 size={14} className="text-surface-400" />
            {demotedCount} auto-compacted
          </div>
        )}
      </div>

      {/* Quick filters row */}
      <QuickFilters />
    </div>
  )
}
