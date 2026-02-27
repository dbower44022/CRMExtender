import { useCallback, useEffect } from 'react'
import { X, ChevronUp, ChevronDown, Maximize2, Minimize2 } from 'lucide-react'
import { useLayoutStore } from '../../stores/layout.ts'
import { useNavigationStore } from '../../stores/navigation.ts'
import { RecordDetail } from '../detail/RecordDetail.tsx'
import { CommunicationPreviewCard } from '../detail/CommunicationPreviewCard.tsx'
import { ConversationPreviewCard } from '../detail/ConversationPreviewCard.tsx'
import { CommunicationFullContent } from '../fullview/CommunicationFullView.tsx'
import { ConversationFullView } from '../fullview/ConversationFullView.tsx'

export function DetailPanel() {
  const hideDetailPanel = useLayoutStore((s) => s.hideDetailPanel)
  const detailPanelExpanded = useLayoutStore((s) => s.detailPanelExpanded)
  const expandDetailPanel = useLayoutStore((s) => s.expandDetailPanel)
  const collapseDetailPanel = useLayoutStore((s) => s.collapseDetailPanel)
  const activeEntityType = useNavigationStore((s) => s.activeEntityType)
  const selectedRowId = useNavigationStore((s) => s.selectedRowId)
  const selectedRowIndex = useNavigationStore((s) => s.selectedRowIndex)
  const loadedRowCount = useNavigationStore((s) => s.loadedRowCount)
  const canGoPrev = selectedRowIndex > 0
  const canGoNext = selectedRowIndex >= 0 && selectedRowIndex < loadedRowCount - 1

  const isExpandedComm = detailPanelExpanded && activeEntityType === 'communication'
  const isExpandedConv = detailPanelExpanded && activeEntityType === 'conversation'

  const handlePrev = useCallback(() => {
    if (!canGoPrev) return
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

  // Escape key: expanded → collapse to preview; preview → close panel
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      // Don't interfere with other modals (search, etc.)
      if ((e.target as HTMLElement)?.closest('[role="dialog"]')) return
      if (detailPanelExpanded) {
        collapseDetailPanel()
      } else {
        hideDetailPanel()
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [detailPanelExpanded, collapseDetailPanel, hideDetailPanel])

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
          {isExpandedComm ? 'Communication' : isExpandedConv ? 'Conversation' : 'Preview'}
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
          {(activeEntityType === 'communication' || activeEntityType === 'conversation') && selectedRowId && (
            (isExpandedComm || isExpandedConv) ? (
              <button
                onClick={collapseDetailPanel}
                className="flex h-6 w-6 items-center justify-center rounded text-surface-400 transition-colors hover:bg-surface-100 hover:text-surface-600"
                title="Collapse to preview"
              >
                <Minimize2 size={14} />
              </button>
            ) : (
              <button
                onClick={expandDetailPanel}
                className="flex h-6 w-6 items-center justify-center rounded text-surface-400 transition-colors hover:bg-surface-100 hover:text-surface-600"
                title="Expand full view"
              >
                <Maximize2 size={14} />
              </button>
            )
          )}
          <button
            onClick={hideDetailPanel}
            className="flex h-6 w-6 items-center justify-center rounded text-surface-400 transition-colors hover:bg-surface-100 hover:text-surface-600"
            title="Close preview"
          >
            <X size={14} />
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-hidden">
        {isExpandedComm ? (
          <CommunicationFullContent
            commId={selectedRowId}
            onNavigateAway={collapseDetailPanel}
          />
        ) : isExpandedConv ? (
          <ConversationFullView
            convId={selectedRowId}
            onNavigateAway={collapseDetailPanel}
          />
        ) : activeEntityType === 'communication' ? (
          <div className="h-full overflow-y-auto">
            <CommunicationPreviewCard entityId={selectedRowId} />
          </div>
        ) : activeEntityType === 'conversation' ? (
          <div className="h-full overflow-y-auto">
            <ConversationPreviewCard entityId={selectedRowId} />
          </div>
        ) : (
          <div className="h-full overflow-y-auto">
            <RecordDetail
              entityType={activeEntityType}
              entityId={selectedRowId}
            />
          </div>
        )}
      </div>
    </div>
  )
}
