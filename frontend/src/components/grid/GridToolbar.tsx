import { useRef, useCallback, useEffect, useState } from 'react'
import {
  Search,
  X,
  Columns3,
  Filter,
  Minimize2,
  Square,
  CheckSquare,
  MinusSquare,
  ChevronDown,
  Plus,
  Upload,
  RefreshCw,
  Calendar,
  MoreHorizontal,
  Pencil,
  Trash2,
  Download,
} from 'lucide-react'
import { toast } from 'sonner'
import { useNavigationStore } from '../../stores/navigation.ts'
import { useViewConfig } from '../../api/views.ts'
import { useGridIntelligenceStore } from '../../stores/gridIntelligence.ts'
import { ColumnPicker } from './ColumnPicker.tsx'
import { FilterBuilder } from './FilterBuilder.tsx'
import { QuickFilters } from './QuickFilters.tsx'

const ENTITY_ACTIONS: Record<string, { label: string; icon: typeof Plus }[]> = {
  contact: [
    { label: 'New Contact', icon: Plus },
    { label: 'Import', icon: Upload },
  ],
  company: [
    { label: 'New Company', icon: Plus },
    { label: 'Import', icon: Upload },
  ],
  communication: [
    { label: 'New Communication', icon: Plus },
    { label: 'Sync Now', icon: RefreshCw },
  ],
  conversation: [
    { label: 'New Conversation', icon: Plus },
  ],
  event: [
    { label: 'New Event', icon: Plus },
    { label: 'Sync Calendars', icon: Calendar },
  ],
  note: [
    { label: 'New Note', icon: Plus },
  ],
  project: [
    { label: 'New Project', icon: Plus },
  ],
}

function SelectionControl() {
  const selectedRowIds = useNavigationStore((s) => s.selectedRowIds)
  const loadedRowCount = useNavigationStore((s) => s.loadedRowCount)
  const selectAllRows = useNavigationStore((s) => s.selectAllRows)
  const deselectAllRows = useNavigationStore((s) => s.deselectAllRows)
  const totalLoaded = loadedRowCount
  const [showDropdown, setShowDropdown] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const selectedCount = selectedRowIds.size
  const allSelected = totalLoaded > 0 && selectedCount === totalLoaded
  const someSelected = selectedCount > 0 && !allSelected

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const CheckIcon = allSelected ? CheckSquare : someSelected ? MinusSquare : Square

  return (
    <div className="flex items-center gap-1" ref={dropdownRef}>
      <button
        onClick={() => {
          if (selectedCount > 0) deselectAllRows()
          else selectAllRows([]) // no-op without IDs; use dropdown
        }}
        className="flex h-8 items-center justify-center rounded-md p-1.5 text-surface-500 hover:bg-surface-100 hover:text-surface-700"
      >
        <CheckIcon size={16} />
      </button>
      <div className="relative">
        <button
          onClick={() => setShowDropdown(!showDropdown)}
          className="flex h-8 items-center justify-center rounded-md p-0.5 text-surface-400 hover:bg-surface-100 hover:text-surface-600"
        >
          <ChevronDown size={14} />
        </button>
        {showDropdown && (
          <div className="absolute left-0 top-full z-20 mt-1 min-w-[140px] rounded-md border border-surface-200 bg-surface-0 py-1 shadow-lg">
            <button
              onClick={() => {
                // Will be wired with actual row IDs from DataGrid via store
                // For now, emit event that DataGrid listens to
                window.dispatchEvent(new CustomEvent('grid:selectAll'))
                setShowDropdown(false)
              }}
              className="flex w-full items-center px-3 py-1.5 text-xs text-surface-600 hover:bg-surface-50"
            >
              Select All
            </button>
            <button
              onClick={() => {
                deselectAllRows()
                setShowDropdown(false)
              }}
              className="flex w-full items-center px-3 py-1.5 text-xs text-surface-600 hover:bg-surface-50"
            >
              Deselect All
            </button>
          </div>
        )}
      </div>
      {selectedCount > 0 && (
        <span className="text-xs font-medium text-primary-600">
          {selectedCount} selected
        </span>
      )}
    </div>
  )
}

function EntityActions() {
  const activeEntityType = useNavigationStore((s) => s.activeEntityType)
  const selectedRowIds = useNavigationStore((s) => s.selectedRowIds)
  const [showOther, setShowOther] = useState(false)
  const otherRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (otherRef.current && !otherRef.current.contains(e.target as Node)) {
        setShowOther(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const selectedCount = selectedRowIds.size
  const actions = ENTITY_ACTIONS[activeEntityType] ?? []

  const btnClass =
    'flex h-8 items-center gap-1.5 rounded-md border border-surface-200 bg-surface-0 px-2.5 text-xs font-medium text-surface-600 hover:bg-surface-50 transition-colors'

  if (selectedCount > 0) {
    return (
      <div className="flex items-center gap-2">
        <button
          onClick={() => toast('Coming soon')}
          className={btnClass}
        >
          <Pencil size={14} />
          Bulk Edit ({selectedCount})
        </button>
        <button
          onClick={() => toast('Coming soon')}
          className={btnClass}
        >
          <Trash2 size={14} />
          Bulk Delete ({selectedCount})
        </button>
        <div className="relative" ref={otherRef}>
          <button
            onClick={() => setShowOther(!showOther)}
            className={btnClass}
          >
            <MoreHorizontal size={14} />
            Other
          </button>
          {showOther && (
            <div className="absolute right-0 top-full z-20 mt-1 min-w-[140px] rounded-md border border-surface-200 bg-surface-0 py-1 shadow-lg">
              <button
                onClick={() => { toast('Coming soon'); setShowOther(false) }}
                className="flex w-full items-center gap-2 px-3 py-1.5 text-xs text-surface-600 hover:bg-surface-50"
              >
                <Download size={12} /> Export
              </button>
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2">
      {actions.map((action) => (
        <button
          key={action.label}
          onClick={() => toast('Coming soon')}
          className={btnClass}
        >
          <action.icon size={14} />
          {action.label}
        </button>
      ))}
      {actions.length > 0 && (
        <div className="relative" ref={otherRef}>
          <button
            onClick={() => setShowOther(!showOther)}
            className={btnClass}
          >
            <MoreHorizontal size={14} />
            Other
          </button>
          {showOther && (
            <div className="absolute right-0 top-full z-20 mt-1 min-w-[140px] rounded-md border border-surface-200 bg-surface-0 py-1 shadow-lg">
              <button
                onClick={() => { toast('Coming soon'); setShowOther(false) }}
                className="flex w-full items-center gap-2 px-3 py-1.5 text-xs text-surface-600 hover:bg-surface-50"
              >
                <Download size={12} /> Export
              </button>
              <button
                onClick={() => { toast('Coming soon'); setShowOther(false) }}
                className="flex w-full items-center gap-2 px-3 py-1.5 text-xs text-surface-600 hover:bg-surface-50"
              >
                <Pencil size={12} /> Bulk Edit
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

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
        {/* Left zone — Selection control */}
        <SelectionControl />

        <div className="mx-1 h-5 w-px bg-surface-200" />

        {/* Center zone — Search, Columns, Filter, Demoted */}
        <div className="flex flex-1 items-center gap-2">
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

        <div className="mx-1 h-5 w-px bg-surface-200" />

        {/* Right zone — Entity actions / Bulk actions */}
        <EntityActions />
      </div>

      {/* Quick filters row */}
      <QuickFilters />
    </div>
  )
}
