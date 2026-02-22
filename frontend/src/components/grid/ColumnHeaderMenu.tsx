import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import {
  ArrowUp,
  ArrowDown,
  X,
  EyeOff,
  Maximize2,
  AlignLeft,
  AlignCenter,
  AlignRight,
  Check,
} from 'lucide-react'
import { useNavigationStore } from '../../stores/navigation.ts'
import { useUpdateViewColumns } from '../../api/views.ts'
import { useGridIntelligenceStore } from '../../stores/gridIntelligence.ts'
import type { EntityDef, View, ViewColumn } from '../../types/api.ts'

interface ColumnHeaderMenuProps {
  x: number
  y: number
  fieldKey: string
  entityDef: EntityDef | undefined
  viewConfig: View | null
  currentSort: string | null
  currentSortDirection: 'asc' | 'desc'
  onClose: () => void
}

const menuItemClass =
  'flex w-full items-center gap-2 px-3 py-1.5 text-xs text-surface-600 hover:bg-surface-50 cursor-pointer'

export function ColumnHeaderMenu({
  x,
  y,
  fieldKey,
  entityDef,
  viewConfig,
  currentSort,
  currentSortDirection,
  onClose,
}: ColumnHeaderMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null)
  const setSort = useNavigationStore((s) => s.setSort)
  const clearSort = useNavigationStore((s) => s.clearSort)
  const updateColumns = useUpdateViewColumns(viewConfig?.id ?? '')
  const saveAlignmentOverride = useGridIntelligenceStore((s) => s.saveAlignmentOverride)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    const keyHandler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('mousedown', handler)
    document.addEventListener('keydown', keyHandler)
    return () => {
      document.removeEventListener('mousedown', handler)
      document.removeEventListener('keydown', keyHandler)
    }
  }, [onClose])

  const fd = entityDef?.fields[fieldKey]
  const isSortedAsc = currentSort === fieldKey && currentSortDirection === 'asc'
  const isSortedDesc = currentSort === fieldKey && currentSortDirection === 'desc'

  const handleSortAsc = () => {
    setSort(fieldKey, 'asc')
    onClose()
  }

  const handleSortDesc = () => {
    setSort(fieldKey, 'desc')
    onClose()
  }

  const handleRemoveSort = () => {
    clearSort()
    onClose()
  }

  const handleHideColumn = () => {
    if (!viewConfig) return
    const cols = viewConfig.columns
      .filter((vc: ViewColumn) => vc.field_key !== fieldKey)
      .map((vc: ViewColumn) => ({
        key: vc.field_key,
        label: vc.label_override || undefined,
        width: vc.width_px || undefined,
      }))
    updateColumns.mutate({ columns: cols })
    onClose()
  }

  const handleAlignment = (alignment: 'left' | 'center' | 'right') => {
    if (saveAlignmentOverride) {
      saveAlignmentOverride(fieldKey, alignment)
    }
    onClose()
  }

  // Adjust position to stay within viewport
  const adjustedX = Math.min(x, window.innerWidth - 200)
  const adjustedY = Math.min(y, window.innerHeight - 300)

  return createPortal(
    <div
      ref={menuRef}
      className="fixed z-50 min-w-[180px] rounded-md border border-surface-200 bg-surface-0 py-1 shadow-lg"
      style={{ left: adjustedX, top: adjustedY }}
    >
      {/* Sort options */}
      {fd?.sortable && (
        <>
          <button onClick={handleSortAsc} className={menuItemClass}>
            <ArrowUp size={12} />
            Sort Ascending
            {isSortedAsc && <Check size={12} className="ml-auto text-primary-600" />}
          </button>
          <button onClick={handleSortDesc} className={menuItemClass}>
            <ArrowDown size={12} />
            Sort Descending
            {isSortedDesc && <Check size={12} className="ml-auto text-primary-600" />}
          </button>
          {(isSortedAsc || isSortedDesc) && (
            <button onClick={handleRemoveSort} className={menuItemClass}>
              <X size={12} />
              Remove Sort
            </button>
          )}
          <div className="my-1 border-t border-surface-200" />
        </>
      )}

      {/* Hide column */}
      <button onClick={handleHideColumn} className={menuItemClass}>
        <EyeOff size={12} />
        Hide Column
      </button>

      {/* Auto-fit width */}
      <button
        onClick={() => {
          // Auto-fit uses canvas measureText from the AGI content analysis
          // For now this is a placeholder that sets a reasonable width
          onClose()
        }}
        className={menuItemClass}
      >
        <Maximize2 size={12} />
        Auto-Fit Width
      </button>

      <div className="my-1 border-t border-surface-200" />

      {/* Data Alignment */}
      <div className="px-3 py-1 text-[10px] font-semibold text-surface-400 uppercase">
        Alignment
      </div>
      <div className="flex items-center gap-1 px-3 py-1">
        <button
          onClick={() => handleAlignment('left')}
          className="rounded p-1 text-surface-400 hover:bg-surface-100 hover:text-surface-600"
          title="Align Left"
        >
          <AlignLeft size={14} />
        </button>
        <button
          onClick={() => handleAlignment('center')}
          className="rounded p-1 text-surface-400 hover:bg-surface-100 hover:text-surface-600"
          title="Align Center"
        >
          <AlignCenter size={14} />
        </button>
        <button
          onClick={() => handleAlignment('right')}
          className="rounded p-1 text-surface-400 hover:bg-surface-100 hover:text-surface-600"
          title="Align Right"
        >
          <AlignRight size={14} />
        </button>
      </div>
    </div>,
    document.body,
  )
}
