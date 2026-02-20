import { useNavigationStore } from '../../stores/navigation.ts'
import { useViews } from '../../api/views.ts'
import { List, ChevronRight } from 'lucide-react'

export function ActionPanel() {
  const activeEntityType = useNavigationStore((s) => s.activeEntityType)
  const activeViewId = useNavigationStore((s) => s.activeViewId)
  const setActiveViewId = useNavigationStore((s) => s.setActiveViewId)
  const { data: views, isLoading } = useViews(activeEntityType)

  const personalViews = views?.filter((v) => v.visibility === 'personal') ?? []
  const sharedViews = views?.filter((v) => v.visibility === 'shared') ?? []

  return (
    <div className="flex h-full flex-col overflow-hidden border-r border-surface-200 bg-surface-50">
      <div className="border-b border-surface-200 px-3 py-2.5">
        <h2 className="text-xs font-semibold tracking-wide text-surface-500 uppercase">
          Views
        </h2>
      </div>

      <div className="flex-1 overflow-y-auto px-2 py-1">
        {isLoading && (
          <div className="space-y-2 p-2">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-7 animate-pulse rounded bg-surface-200"
              />
            ))}
          </div>
        )}

        {personalViews.length > 0 && (
          <ViewGroup
            label="My Views"
            views={personalViews}
            activeViewId={activeViewId}
            onSelect={setActiveViewId}
          />
        )}

        {sharedViews.length > 0 && (
          <ViewGroup
            label="Shared"
            views={sharedViews}
            activeViewId={activeViewId}
            onSelect={setActiveViewId}
          />
        )}
      </div>
    </div>
  )
}

interface ViewGroupProps {
  label: string
  views: Array<{
    id: string
    name: string
    is_default: number
  }>
  activeViewId: string | null
  onSelect: (id: string) => void
}

function ViewGroup({ label, views, activeViewId, onSelect }: ViewGroupProps) {
  return (
    <div className="mb-2">
      <div className="px-2 py-1.5 text-[10px] font-semibold tracking-wider text-surface-400 uppercase">
        {label}
      </div>
      {views.map((v) => {
        const isActive = v.id === activeViewId
        return (
          <button
            key={v.id}
            onClick={() => onSelect(v.id)}
            className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors ${
              isActive
                ? 'bg-primary-50 font-medium text-primary-700'
                : 'text-surface-600 hover:bg-surface-100'
            }`}
          >
            <List size={14} className="shrink-0" />
            <span className="truncate">{v.name}</span>
            {isActive && (
              <ChevronRight size={12} className="ml-auto shrink-0" />
            )}
          </button>
        )
      })}
    </div>
  )
}
