import { useCallback } from 'react'
import { X, ChevronUp, ChevronDown } from 'lucide-react'
import { useLayoutStore } from '../../stores/layout.ts'
import { useNavigationStore } from '../../stores/navigation.ts'
import { RecordDetail } from '../detail/RecordDetail.tsx'

export function DetailPanel() {
  const hideDetailPanel = useLayoutStore((s) => s.hideDetailPanel)
  const activeEntityType = useNavigationStore((s) => s.activeEntityType)
  const selectedRowId = useNavigationStore((s) => s.selectedRowId)
  const selectedRowIndex = useNavigationStore((s) => s.selectedRowIndex)
  const loadedRowCount = useNavigationStore((s) => s.loadedRowCount)
  const setSelectedRow = useNavigationStore((s) => s.setSelectedRow)

  const canGoPrev = selectedRowIndex > 0
  const canGoNext = selectedRowIndex >= 0 && selectedRowIndex < loadedRowCount - 1

  const handlePrev = useCallback(() => {
    if (!canGoPrev) return
    // We need to read the rows from the grid — dispatch a custom event
    window.dispatchEvent(
      new CustomEvent('detailPanel:navigate', { detail: { direction: -1 } }),
    )
  }, [canGoPrev])

  const handleNext = useCallback(() => {
    if (!canGoNext) return
    window.dispatchEvent(
      new CustomEvent('detailPanel:navigate', { detail: { direction: 1 } }),
    )
  }, [canGoNext])

  if (!selectedRowId) {
    return (
      <div className="flex h-full items-center justify-center bg-surface-50 p-6 text-center">
        <p className="text-sm text-surface-400">
          Select a record to preview
        </p>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col bg-surface-0">
      <div className="flex items-center justify-between border-b border-surface-200 px-4 py-2">
        <span className="text-xs font-medium text-surface-500 uppercase">
          Preview
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={handlePrev}
            disabled={!canGoPrev}
            className="flex h-6 w-6 items-center justify-center rounded text-surface-400 transition-colors hover:bg-surface-100 hover:text-surface-600 disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:text-surface-400"
            title="Previous record"
          >
            <ChevronUp size={14} />
          </button>
          <button
            onClick={handleNext}
            disabled={!canGoNext}
            className="flex h-6 w-6 items-center justify-center rounded text-surface-400 transition-colors hover:bg-surface-100 hover:text-surface-600 disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:text-surface-400"
            title="Next record"
          >
            <ChevronDown size={14} />
          </button>
          <button
            onClick={hideDetailPanel}
            className="flex h-6 w-6 items-center justify-center rounded text-surface-400 transition-colors hover:bg-surface-100 hover:text-surface-600"
            title="Close preview"
          >
            <X size={14} />
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">
        <RecordDetail
          entityType={activeEntityType}
          entityId={selectedRowId}
        />
      </div>
    </div>
  )
}
