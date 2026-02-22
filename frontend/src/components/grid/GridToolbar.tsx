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
  HelpCircle,
  Tag,
  Archive,
  Merge,
  Sparkles,
  UserCheck,
  Settings2,
} from 'lucide-react'
import { toast } from 'sonner'
import { useNavigationStore } from '../../stores/navigation.ts'
import { useViewConfig } from '../../api/views.ts'
import { useGridIntelligenceStore } from '../../stores/gridIntelligence.ts'
import { ColumnPicker } from './ColumnPicker.tsx'
import { FilterBuilder } from './FilterBuilder.tsx'
import { QuickFilters } from './QuickFilters.tsx'
import { MergeContactsModal } from './MergeContactsModal.tsx'
import { MergeCompaniesModal } from './MergeCompaniesModal.tsx'
import { AddContactModal } from './AddContactModal.tsx'
import { AddCompanyModal } from './AddCompanyModal.tsx'
import { GridDisplaySettings } from './GridDisplaySettings.tsx'
import { ToolbarContextMenu } from './ToolbarContextMenu.tsx'

interface EntityActionConfig {
  primary: { label: string; icon: typeof Plus }[]
  other: { label: string; icon: typeof Plus }[]
}

const ENTITY_ACTIONS: Record<string, EntityActionConfig> = {
  contact: {
    primary: [
      { label: 'Add Contact', icon: Plus },
      { label: 'Import', icon: Upload },
    ],
    other: [
      { label: 'Export', icon: Download },
      { label: 'Merge Duplicates', icon: Merge },
      { label: 'Bulk Edit', icon: Pencil },
    ],
  },
  company: {
    primary: [
      { label: 'Add Company', icon: Plus },
      { label: 'Import', icon: Upload },
    ],
    other: [
      { label: 'Export', icon: Download },
      { label: 'Enrich All', icon: Sparkles },
      { label: 'Bulk Edit', icon: Pencil },
    ],
  },
  communication: {
    primary: [
      { label: 'Add Communication', icon: Plus },
      { label: 'Sync Now', icon: RefreshCw },
    ],
    other: [
      { label: 'Export', icon: Download },
      { label: 'Bulk Assign', icon: UserCheck },
    ],
  },
  conversation: {
    primary: [
      { label: 'Add Conversation', icon: Plus },
    ],
    other: [
      { label: 'Export', icon: Download },
      { label: 'Bulk Merge', icon: Merge },
    ],
  },
  event: {
    primary: [
      { label: 'Add Event', icon: Plus },
      { label: 'Sync Calendars', icon: Calendar },
    ],
    other: [
      { label: 'Export', icon: Download },
      { label: 'Bulk Edit', icon: Pencil },
    ],
  },
  note: {
    primary: [
      { label: 'Add Note', icon: Plus },
    ],
    other: [
      { label: 'Export', icon: Download },
      { label: 'Bulk Tag', icon: Tag },
    ],
  },
  project: {
    primary: [
      { label: 'Add Project', icon: Plus },
    ],
    other: [
      { label: 'Export', icon: Download },
      { label: 'Archive', icon: Archive },
    ],
  },
}

const BULK_OTHER_ITEMS: { label: string; icon: typeof Plus }[] = [
  { label: 'Bulk Assign', icon: UserCheck },
  { label: 'Bulk Export', icon: Download },
  { label: 'Bulk Tag', icon: Tag },
  { label: 'Bulk Archive', icon: Archive },
]

const comingSoon = () => toast('Coming soon')

const btnClass =
  'flex h-8 items-center gap-1.5 rounded-md border border-surface-200 bg-surface-0 px-2.5 text-xs font-medium text-surface-600 hover:bg-surface-50 transition-colors whitespace-nowrap'

const dropdownItemClass =
  'flex w-full items-center gap-2 px-3 py-1.5 text-xs text-surface-600 hover:bg-surface-50'

const dropdownClass =
  'absolute top-full z-50 mt-1 min-w-[160px] rounded-md border border-surface-200 bg-surface-0 py-1 shadow-lg'

function SelectionControl({
  showColumns,
  setShowColumns,
  setShowFilters,
}: {
  showColumns: boolean
  setShowColumns: (v: boolean) => void
  setShowFilters: (v: boolean) => void
}) {
  const selectedRowIds = useNavigationStore((s) => s.selectedRowIds)
  const loadedRowCount = useNavigationStore((s) => s.loadedRowCount)
  const deselectAllRows = useNavigationStore((s) => s.deselectAllRows)
  const [showDropdown, setShowDropdown] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const selectedCount = selectedRowIds.size
  const allSelected = loadedRowCount > 0 && selectedCount === loadedRowCount
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

  // Selection active state — show "N selected ▾"
  if (selectedCount > 0) {
    return (
      <div className="flex items-center gap-2" ref={dropdownRef}>
        <div className="relative">
          <button
            onClick={() => setShowDropdown(!showDropdown)}
            className="flex h-8 items-center gap-1.5 rounded-md px-2 text-xs font-medium text-primary-600 hover:bg-primary-50"
          >
            <CheckIcon size={16} />
            {selectedCount} selected
            <ChevronDown size={12} />
          </button>
          {showDropdown && (
            <div className={`${dropdownClass} left-0`}>
              <button
                onClick={() => {
                  window.dispatchEvent(new CustomEvent('grid:selectAll'))
                  setShowDropdown(false)
                }}
                className={dropdownItemClass}
              >
                Select All
              </button>
              <button
                onClick={() => {
                  deselectAllRows()
                  setShowDropdown(false)
                }}
                className={dropdownItemClass}
              >
                Deselect All
              </button>
              <button
                onClick={() => {
                  window.dispatchEvent(new CustomEvent('grid:invertSelection'))
                  setShowDropdown(false)
                }}
                className={dropdownItemClass}
              >
                Invert Selection
              </button>
            </div>
          )}
        </div>

        {/* Columns button stays in left zone during selection */}
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
      </div>
    )
  }

  // Default state — checkbox + dropdown + Columns
  return (
    <div className="flex items-center gap-2" ref={dropdownRef}>
      <div className="flex items-center gap-0.5">
        <button
          onClick={() => {
            if (selectedCount > 0) deselectAllRows()
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
            <div className={`${dropdownClass} left-0`}>
              <button
                onClick={() => {
                  window.dispatchEvent(new CustomEvent('grid:selectAll'))
                  setShowDropdown(false)
                }}
                className={dropdownItemClass}
              >
                Select All
              </button>
              <button
                onClick={() => {
                  deselectAllRows()
                  setShowDropdown(false)
                }}
                className={dropdownItemClass}
              >
                Deselect All
              </button>
              <button
                onClick={() => {
                  window.dispatchEvent(new CustomEvent('grid:invertSelection'))
                  setShowDropdown(false)
                }}
                className={dropdownItemClass}
              >
                Invert Selection
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Columns button — in left zone per PRD */}
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
    </div>
  )
}

function EntityActions() {
  const activeEntityType = useNavigationStore((s) => s.activeEntityType)
  const selectedRowIds = useNavigationStore((s) => s.selectedRowIds)
  const [showOther, setShowOther] = useState(false)
  const [showMergeModal, setShowMergeModal] = useState(false)
  const [showAddModal, setShowAddModal] = useState(false)
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
  const config = ENTITY_ACTIONS[activeEntityType] ?? { primary: [], other: [] }

  // Build bulk Other items — add Merge Duplicates for contacts and companies
  const hasMerge = activeEntityType === 'contact' || activeEntityType === 'company'
  const bulkOtherItems = hasMerge
    ? [{ label: 'Merge Duplicates', icon: Merge }, ...BULK_OTHER_ITEMS]
    : BULK_OTHER_ITEMS

  const entityLabel = activeEntityType === 'contact' ? 'contacts' : 'companies'

  const handleActionClick = (label: string) => {
    if (label === 'Add Contact' || label === 'Add Company') {
      setShowAddModal(true)
    } else {
      comingSoon()
    }
  }

  const handleBulkOtherClick = (label: string) => {
    if (label === 'Merge Duplicates' && hasMerge) {
      if (selectedCount < 2) {
        toast.info(`Select at least 2 ${entityLabel} to merge`)
      } else {
        setShowMergeModal(true)
      }
    } else {
      comingSoon()
    }
    setShowOther(false)
  }

  // Selection active — bulk action buttons
  if (selectedCount > 0) {
    return (
      <div className="flex items-center gap-2">
        <button onClick={comingSoon} className={btnClass}>
          <Pencil size={14} />
          Bulk Edit ({selectedCount})
        </button>
        <button onClick={comingSoon} className={btnClass}>
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
            <div className={`${dropdownClass} right-0`}>
              {bulkOtherItems.map((item) => (
                <button
                  key={item.label}
                  onClick={() => handleBulkOtherClick(item.label)}
                  className={dropdownItemClass}
                >
                  <item.icon size={12} /> {item.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {showMergeModal && activeEntityType === 'contact' && (
          <MergeContactsModal
            contactIds={Array.from(selectedRowIds)}
            onClose={() => setShowMergeModal(false)}
          />
        )}
        {showMergeModal && activeEntityType === 'company' && (
          <MergeCompaniesModal
            companyIds={Array.from(selectedRowIds)}
            onClose={() => setShowMergeModal(false)}
          />
        )}
      </div>
    )
  }

  // Default — entity-specific primary actions + Other overflow
  return (
    <div className="flex items-center gap-2">
      {config.primary.map((action) => (
        <button key={action.label} onClick={() => handleActionClick(action.label)} className={btnClass}>
          <action.icon size={14} />
          {action.label}
        </button>
      ))}
      <div className="relative" ref={otherRef}>
        <button
          onClick={() => setShowOther(!showOther)}
          className={btnClass}
        >
          <MoreHorizontal size={14} />
          Other
        </button>
        {showOther && (
          <div className={`${dropdownClass} right-0`}>
            {/* Primary actions repeated at top */}
            {config.primary.map((action) => (
              <button
                key={action.label}
                onClick={() => { handleActionClick(action.label); setShowOther(false) }}
                className={dropdownItemClass}
              >
                <action.icon size={12} /> {action.label}
              </button>
            ))}
            {/* Separator */}
            <div className="my-1 border-t border-surface-200" />
            {/* Additional actions */}
            {config.other.map((action) => (
              <button
                key={action.label}
                onClick={() => { comingSoon(); setShowOther(false) }}
                className={dropdownItemClass}
              >
                <action.icon size={12} /> {action.label}
              </button>
            ))}
            {/* Separator + Help */}
            <div className="my-1 border-t border-surface-200" />
            <button
              onClick={() => { comingSoon(); setShowOther(false) }}
              className={dropdownItemClass}
            >
              <HelpCircle size={12} /> Help
            </button>
          </div>
        )}
      </div>

      {showAddModal && activeEntityType === 'contact' && (
        <AddContactModal onClose={() => setShowAddModal(false)} />
      )}
      {showAddModal && activeEntityType === 'company' && (
        <AddCompanyModal onClose={() => setShowAddModal(false)} />
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
  const [showDisplaySettings, setShowDisplaySettings] = useState(false)
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number } | null>(null)

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

  const handleToolbarContext = (e: React.MouseEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement
    if (target.closest('input, textarea')) return
    e.preventDefault()
    setContextMenu({ x: e.clientX, y: e.clientY })
  }

  const handleContextAction = useCallback((action: string) => {
    setContextMenu(null)
    switch (action) {
      case 'columns':
        setShowColumns(true)
        setShowFilters(false)
        setShowDisplaySettings(false)
        break
      case 'filters':
        setShowFilters(true)
        setShowColumns(false)
        setShowDisplaySettings(false)
        break
      case 'display':
        setShowDisplaySettings(true)
        setShowColumns(false)
        setShowFilters(false)
        break
      default:
        toast('Coming soon')
    }
  }, [])

  return (
    <div
      className="border-b border-surface-200 px-4 py-2"
      onContextMenu={handleToolbarContext}
      onDoubleClick={handleToolbarContext}
    >
      <div className="flex min-w-0 items-center gap-2">
        {/* Left zone — Selection control + Columns */}
        <div className="shrink-0">
          <SelectionControl
            showColumns={showColumns}
            setShowColumns={setShowColumns}
            setShowFilters={setShowFilters}
          />
        </div>

        <div className="mx-1 h-5 w-px shrink-0 bg-surface-200" />

        {/* Center zone — Search, Filter, Demoted */}
        <div className="flex min-w-0 flex-1 items-center justify-center gap-2">
          <div className="relative min-w-0 flex-1 max-w-sm">
            <Search
              size={14}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-surface-400"
            />
            <input
              ref={inputRef}
              type="text"
              value={localSearch}
              onChange={(e) => handleChange(e.target.value)}
              placeholder="Search this view..."
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

          {/* Display settings button */}
          <div className="relative">
            <button
              onClick={() => {
                setShowDisplaySettings(!showDisplaySettings)
                setShowColumns(false)
                setShowFilters(false)
              }}
              className={`flex h-8 items-center gap-1.5 rounded-md border px-2.5 text-xs font-medium transition-colors ${
                showDisplaySettings
                  ? 'border-primary-300 bg-primary-50 text-primary-700'
                  : 'border-surface-200 bg-surface-0 text-surface-600 hover:bg-surface-50'
              }`}
            >
              <Settings2 size={14} />
              Display
            </button>
            {showDisplaySettings && (
              <GridDisplaySettings onClose={() => setShowDisplaySettings(false)} />
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

        <div className="mx-1 h-5 w-px shrink-0 bg-surface-200" />

        {/* Right zone — Entity actions / Bulk actions */}
        <div className="shrink-0">
          <EntityActions />
        </div>
      </div>

      {/* Quick filters row */}
      <QuickFilters />

      {contextMenu && (
        <ToolbarContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          onClose={() => setContextMenu(null)}
          onAction={handleContextAction}
        />
      )}
    </div>
  )
}
