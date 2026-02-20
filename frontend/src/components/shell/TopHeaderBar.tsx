import { Search } from 'lucide-react'
import { useNavigationStore } from '../../stores/navigation.ts'
import { useEntityRegistry } from '../../api/registry.ts'
import { useViewConfig } from '../../api/views.ts'

export function TopHeaderBar() {
  const activeEntityType = useNavigationStore((s) => s.activeEntityType)
  const activeViewId = useNavigationStore((s) => s.activeViewId)
  const { data: registry } = useEntityRegistry()
  const { data: viewConfig } = useViewConfig(activeViewId)

  const entityLabel = registry?.[activeEntityType]?.label ?? activeEntityType
  const viewName = viewConfig?.name

  return (
    <header className="flex h-[48px] items-center border-b border-surface-200 bg-surface-0 px-4">
      <nav className="flex items-center gap-1.5 text-sm">
        <span className="font-medium text-surface-700">{entityLabel}</span>
        {viewName && (
          <>
            <span className="text-surface-400">/</span>
            <span className="text-surface-500">{viewName}</span>
          </>
        )}
      </nav>

      <div className="ml-auto flex items-center gap-3">
        <button
          className="flex h-8 items-center gap-2 rounded-lg border border-surface-200 bg-surface-50 px-3 text-xs text-surface-400 transition-colors hover:border-surface-300"
          title="Search (Ctrl+K)"
        >
          <Search size={14} />
          <span>Search...</span>
          <kbd className="ml-3 rounded border border-surface-200 bg-surface-100 px-1.5 py-0.5 text-[10px] font-medium text-surface-400">
            Ctrl K
          </kbd>
        </button>
      </div>
    </header>
  )
}
