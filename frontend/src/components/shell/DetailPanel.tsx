import { X } from 'lucide-react'
import { useLayoutStore } from '../../stores/layout.ts'
import { useNavigationStore } from '../../stores/navigation.ts'
import { RecordDetail } from '../detail/RecordDetail.tsx'

export function DetailPanel() {
  const hideDetailPanel = useLayoutStore((s) => s.hideDetailPanel)
  const activeEntityType = useNavigationStore((s) => s.activeEntityType)
  const selectedRowId = useNavigationStore((s) => s.selectedRowId)

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
        <button
          onClick={hideDetailPanel}
          className="flex h-6 w-6 items-center justify-center rounded text-surface-400 transition-colors hover:bg-surface-100 hover:text-surface-600"
          title="Close preview"
        >
          <X size={14} />
        </button>
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
