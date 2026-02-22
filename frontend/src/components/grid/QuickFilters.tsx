import { useNavigationStore } from '../../stores/navigation.ts'
import type { QuickFilter } from '../../types/api.ts'

interface QuickFilterDef {
  label: string
  filter: QuickFilter
}

const QUICK_FILTERS: Record<string, QuickFilterDef[]> = {
  contact: [
    { label: 'Active', filter: { field_key: 'status', operator: 'equals', value: 'active' } },
    { label: 'Inactive', filter: { field_key: 'status', operator: 'equals', value: 'inactive' } },
  ],
  company: [
    { label: 'Active', filter: { field_key: 'status', operator: 'equals', value: 'active' } },
  ],
  conversation: [
    { label: 'Open', filter: { field_key: 'status', operator: 'equals', value: 'open' } },
    { label: 'Closed', filter: { field_key: 'status', operator: 'equals', value: 'closed' } },
  ],
  event: [
    { label: 'Upcoming', filter: { field_key: 'start', operator: 'is_after', value: new Date().toISOString().slice(0, 10) } },
  ],
}

export function QuickFilters() {
  const activeEntityType = useNavigationStore((s) => s.activeEntityType)
  const quickFilters = useNavigationStore((s) => s.quickFilters)
  const toggleQuickFilter = useNavigationStore((s) => s.toggleQuickFilter)

  const defs = QUICK_FILTERS[activeEntityType]
  if (!defs || defs.length === 0) return null

  return (
    <div className="flex items-center gap-1.5 pt-1.5">
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
    </div>
  )
}
