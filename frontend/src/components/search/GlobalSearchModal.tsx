import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { createPortal } from 'react-dom'
import { Search, X, ArrowLeft, Loader2 } from 'lucide-react'
import { useGlobalSearch, type SearchResultItem, type SearchGroup } from '../../api/search.ts'
import { useLayoutStore } from '../../stores/layout.ts'
import { useNavigationStore } from '../../stores/navigation.ts'
import { ENTITY_ICONS } from '../../lib/entityIcons.ts'
import { RecordDetail } from '../detail/RecordDetail.tsx'

type Mode =
  | { kind: 'search' }
  | { kind: 'detail'; entityType: string; entityId: string; entityName: string }
  | { kind: 'expanded'; entityType: string; label: string }

interface FlatItem {
  entityType: string
  item: SearchResultItem
}

export function GlobalSearchModal() {
  const closeSearchModal = useLayoutStore((s) => s.closeSearchModal)
  const setActiveEntityType = useNavigationStore((s) => s.setActiveEntityType)
  const setPendingNavigation = useNavigationStore((s) => s.setPendingNavigation)
  const showDetailPanel = useLayoutStore((s) => s.showDetailPanel)

  const [mode, setMode] = useState<Mode>({ kind: 'search' })
  const [inputValue, setInputValue] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [focusedIndex, setFocusedIndex] = useState(-1)

  const inputRef = useRef<HTMLInputElement>(null)
  const resultsRef = useRef<HTMLDivElement>(null)

  // Debounce input → query
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(inputValue), 300)
    return () => clearTimeout(timer)
  }, [inputValue])

  // Search hooks
  const searchQuery = mode.kind === 'expanded' ? debouncedQuery : debouncedQuery
  const expandedType = mode.kind === 'expanded' ? mode.entityType : undefined
  const expandedLimit = mode.kind === 'expanded' ? 50 : undefined

  const { data: searchData, isLoading } = useGlobalSearch(searchQuery, {
    entityType: expandedType,
    limit: expandedLimit,
  })

  // Also keep the grouped data for returning from expanded mode
  const { data: groupedData } = useGlobalSearch(debouncedQuery, {
    entityType: undefined,
    limit: undefined,
  })

  const displayData = mode.kind === 'expanded' ? searchData : groupedData

  // Flatten results for keyboard navigation
  const flatItems = useMemo<FlatItem[]>(() => {
    if (!displayData?.groups) return []
    const items: FlatItem[] = []
    for (const group of displayData.groups) {
      for (const item of group.results) {
        items.push({ entityType: group.entity_type, item })
      }
    }
    return items
  }, [displayData])

  // Reset focused index when results change
  useEffect(() => {
    setFocusedIndex(flatItems.length > 0 ? 0 : -1)
  }, [flatItems.length])

  // Auto-focus input on mount and when returning to search mode
  useEffect(() => {
    if (mode.kind === 'search' || mode.kind === 'expanded') {
      inputRef.current?.focus()
    }
  }, [mode.kind])

  const goBack = useCallback(() => {
    if (mode.kind === 'detail' || mode.kind === 'expanded') {
      setMode({ kind: 'search' })
    } else {
      closeSearchModal()
    }
  }, [mode.kind, closeSearchModal])

  const openDetail = useCallback((entityType: string, entityId: string, entityName: string) => {
    setMode({ kind: 'detail', entityType, entityId, entityName })
  }, [])

  const navigateToGrid = useCallback(
    (entityType: string, entityId: string) => {
      const currentEntityType = useNavigationStore.getState().activeEntityType
      setPendingNavigation({ entityType, entityId })
      if (currentEntityType !== entityType) {
        setActiveEntityType(entityType)
      }
      showDetailPanel()
      closeSearchModal()
    },
    [setActiveEntityType, setPendingNavigation, showDetailPanel, closeSearchModal],
  )

  const handleShowAll = useCallback(
    (group: SearchGroup) => {
      setMode({ kind: 'expanded', entityType: group.entity_type, label: group.label })
      setFocusedIndex(0)
    },
    [],
  )

  // Keyboard navigation
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (mode.kind === 'detail') {
        if (e.key === 'Escape') {
          e.preventDefault()
          goBack()
        }
        return
      }

      if (e.key === 'Escape') {
        e.preventDefault()
        if (mode.kind === 'expanded') {
          setMode({ kind: 'search' })
        } else {
          closeSearchModal()
        }
        return
      }

      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setFocusedIndex((prev) => Math.min(prev + 1, flatItems.length - 1))
        return
      }

      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setFocusedIndex((prev) => Math.max(prev - 1, 0))
        return
      }

      if (e.key === 'Enter' && focusedIndex >= 0 && focusedIndex < flatItems.length) {
        e.preventDefault()
        const { entityType, item } = flatItems[focusedIndex]
        if (e.shiftKey) {
          navigateToGrid(entityType, item.id)
        } else {
          openDetail(entityType, item.id, item.name)
        }
        return
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [mode, flatItems, focusedIndex, goBack, closeSearchModal, navigateToGrid, openDetail])

  // Scroll focused item into view
  useEffect(() => {
    if (focusedIndex < 0) return
    const el = resultsRef.current?.querySelector(`[data-search-index="${focusedIndex}"]`)
    el?.scrollIntoView({ block: 'nearest' })
  }, [focusedIndex])

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) closeSearchModal()
  }

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex justify-center bg-black/50 pt-[10vh]"
      onClick={handleBackdropClick}
    >
      <div
        className="flex h-fit max-h-[80vh] w-full max-w-3xl flex-col rounded-lg bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {mode.kind === 'detail' ? (
          <DetailView
            entityType={mode.entityType}
            entityId={mode.entityId}
            entityName={mode.entityName}
            onBack={goBack}
            onClose={closeSearchModal}
            onNavigateToGrid={() => navigateToGrid(mode.entityType, mode.entityId)}
          />
        ) : (
          <>
            {/* Search input */}
            <div className="flex items-center gap-3 border-b border-surface-200 px-4 py-3">
              {mode.kind === 'expanded' ? (
                <button
                  onClick={goBack}
                  className="rounded-md p-1 text-surface-400 hover:bg-surface-100 hover:text-surface-600"
                >
                  <ArrowLeft size={18} />
                </button>
              ) : (
                <Search size={18} className="shrink-0 text-surface-400" />
              )}
              <input
                ref={inputRef}
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder={
                  mode.kind === 'expanded'
                    ? `Search ${mode.label}...`
                    : 'Search across all records...'
                }
                className="flex-1 bg-transparent text-sm text-surface-800 outline-none placeholder:text-surface-400"
                autoFocus
              />
              {inputValue && (
                <button
                  onClick={() => {
                    setInputValue('')
                    inputRef.current?.focus()
                  }}
                  className="rounded-md p-1 text-surface-400 hover:bg-surface-100 hover:text-surface-600"
                >
                  <X size={16} />
                </button>
              )}
              <kbd className="hidden rounded border border-surface-200 bg-surface-100 px-1.5 py-0.5 text-[10px] font-medium text-surface-400 sm:block">
                ESC
              </kbd>
            </div>

            {/* Results */}
            <div ref={resultsRef} className="flex-1 overflow-y-auto">
              {!debouncedQuery && (
                <div className="px-4 py-8 text-center text-sm text-surface-400">
                  Type to search contacts, companies, conversations, and more...
                </div>
              )}

              {debouncedQuery && isLoading && (
                <div className="flex items-center justify-center gap-2 px-4 py-8 text-sm text-surface-400">
                  <Loader2 size={16} className="animate-spin" />
                  Searching...
                </div>
              )}

              {debouncedQuery && !isLoading && displayData && displayData.groups.length === 0 && (
                <div className="px-4 py-8 text-center text-sm text-surface-400">
                  No matching records found
                </div>
              )}

              {debouncedQuery && !isLoading && displayData && displayData.groups.length > 0 && (
                <GroupedResults
                  groups={displayData.groups}
                  flatItems={flatItems}
                  focusedIndex={focusedIndex}
                  onHover={setFocusedIndex}
                  onSelect={(entityType, item) => openDetail(entityType, item.id, item.name)}
                  onShiftSelect={(entityType, item) => navigateToGrid(entityType, item.id)}
                  onShowAll={mode.kind !== 'expanded' ? handleShowAll : undefined}
                />
              )}
            </div>

            {/* Footer hints */}
            {debouncedQuery && displayData && displayData.groups.length > 0 && (
              <div className="flex items-center gap-4 border-t border-surface-200 px-4 py-2 text-[11px] text-surface-400">
                <span className="flex items-center gap-1">
                  <kbd className="rounded border border-surface-200 bg-surface-50 px-1 py-0.5 font-mono">
                    ↑↓
                  </kbd>
                  navigate
                </span>
                <span className="flex items-center gap-1">
                  <kbd className="rounded border border-surface-200 bg-surface-50 px-1 py-0.5 font-mono">
                    ↵
                  </kbd>
                  preview
                </span>
                <span className="flex items-center gap-1">
                  <kbd className="rounded border border-surface-200 bg-surface-50 px-1 py-0.5 font-mono">
                    ⇧↵
                  </kbd>
                  go to record
                </span>
              </div>
            )}
          </>
        )}
      </div>
    </div>,
    document.body,
  )
}

// -- Sub-components --

function GroupedResults({
  groups,
  flatItems,
  focusedIndex,
  onHover,
  onSelect,
  onShiftSelect,
  onShowAll,
}: {
  groups: SearchGroup[]
  flatItems: FlatItem[]
  focusedIndex: number
  onHover: (index: number) => void
  onSelect: (entityType: string, item: SearchResultItem) => void
  onShiftSelect: (entityType: string, item: SearchResultItem) => void
  onShowAll?: (group: SearchGroup) => void
}) {
  let runningIndex = 0

  return (
    <div className="py-1">
      {groups.map((group) => {
        const Icon = ENTITY_ICONS[group.entity_type]
        const groupStartIndex = runningIndex
        const items = group.results

        const rows = items.map((item, i) => {
          const flatIdx = groupStartIndex + i
          return (
            <ResultRow
              key={item.id}
              entityType={group.entity_type}
              item={item}
              flatIndex={flatIdx}
              isFocused={flatIdx === focusedIndex}
              onHover={onHover}
              onSelect={onSelect}
              onShiftSelect={onShiftSelect}
            />
          )
        })

        runningIndex += items.length

        return (
          <div key={group.entity_type}>
            <div className="flex items-center gap-2 px-4 py-1.5">
              {Icon && <Icon size={14} className="text-surface-400" />}
              <span className="text-xs font-semibold text-surface-500">
                {group.label}
              </span>
              <span className="text-xs text-surface-400">({group.total})</span>
              {onShowAll && group.total > group.results.length && (
                <button
                  onClick={() => onShowAll(group)}
                  className="ml-auto text-xs text-primary-600 hover:text-primary-700"
                >
                  Show all {group.total}
                </button>
              )}
            </div>
            {rows}
          </div>
        )
      })}
    </div>
  )
}

function ResultRow({
  entityType,
  item,
  flatIndex,
  isFocused,
  onHover,
  onSelect,
  onShiftSelect,
}: {
  entityType: string
  item: SearchResultItem
  flatIndex: number
  isFocused: boolean
  onHover: (index: number) => void
  onSelect: (entityType: string, item: SearchResultItem) => void
  onShiftSelect: (entityType: string, item: SearchResultItem) => void
}) {
  const Icon = ENTITY_ICONS[entityType]

  return (
    <div
      data-search-index={flatIndex}
      className={`flex cursor-pointer items-center gap-3 px-4 py-2 ${
        isFocused ? 'bg-primary-50' : 'hover:bg-surface-50'
      }`}
      onMouseEnter={() => onHover(flatIndex)}
      onClick={(e) => {
        if (e.shiftKey) {
          onShiftSelect(entityType, item)
        } else {
          onSelect(entityType, item)
        }
      }}
    >
      {Icon && <Icon size={16} className="shrink-0 text-surface-400" />}
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium text-surface-800">{item.name}</div>
        {item.subtitle && (
          <div className="truncate text-xs text-surface-500">{item.subtitle}</div>
        )}
      </div>
      {item.secondary && (
        <div className="shrink-0 truncate text-xs text-surface-400 max-w-[200px]">
          {item.secondary}
        </div>
      )}
    </div>
  )
}

function DetailView({
  entityType,
  entityId,
  entityName,
  onBack,
  onClose,
  onNavigateToGrid,
}: {
  entityType: string
  entityId: string
  entityName: string
  onBack: () => void
  onClose: () => void
  onNavigateToGrid: () => void
}) {
  return (
    <>
      <div className="flex items-center gap-2 border-b border-surface-200 px-4 py-3">
        <button
          onClick={onBack}
          className="rounded-md p-1 text-surface-400 hover:bg-surface-100 hover:text-surface-600"
        >
          <ArrowLeft size={18} />
        </button>
        <span className="truncate text-sm font-medium text-surface-700">{entityName}</span>
        <span className="text-xs text-surface-400">({entityType})</span>
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={onNavigateToGrid}
            className="rounded-md px-2.5 py-1 text-xs font-medium text-primary-600 hover:bg-primary-50"
          >
            Go to record
          </button>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-surface-400 hover:bg-surface-100 hover:text-surface-600"
          >
            <X size={18} />
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">
        <RecordDetail entityType={entityType} entityId={entityId} />
      </div>
    </>
  )
}
