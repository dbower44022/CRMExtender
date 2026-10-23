import { useNavigationStore } from '../../stores/navigation.ts'
import { QUICK_FILTERS } from '../../lib/quickFilterDefs.ts'

export function QuickFilters() {
  const activeEntityType = useNavigationStore((s) => s.activeEntityType)
  const quickFilters = useNavigationStore((s) => s.quickFilters)
  const toggleQuickFilter = useNavigationStore((s) => s.toggleQuickFilter)

  const defs = QUICK_FILTERS[activeEntityType]
  if (!defs || defs.length === 0) return null

  // Done conversations are hidden until a status chip is active (Base PRD §6.4).
  const doneHidden =
    activeEntityType === 'conversation' && !quickFilters.some((qf) => qf.field_key === 'status')

  return (
    <div className="flex flex-wrap items-center gap-1.5 pt-1.5">
      {defs.map((def) => {
        const isActive = quickFilters.some(
          (qf) =>
            qf.field_key === def.filter.field_key &&
            qf.operator === def.filter.operator &&
            qf.value === def.filter.value,
        )
        return (
          <button
            key={def.label}
            onClick={() => toggleQuickFilter(def.filter)}
            className={`rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors ${
              isActive
                ? 'border-primary-300 bg-primary-50 text-primary-700'
                : 'border-surface-200 bg-surface-0 text-surface-500 hover:border-surface-300 hover:text-surface-600'
            }`}
          >
            {def.label}
          </button>
        )
      })}
      {doneHidden && (
        <span className="text-[11px] text-surface-400">Done conversations are hidden. Click Done to see them.</span>
      )}
    </div>
  )
}
