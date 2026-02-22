import { useState, useRef, useEffect } from 'react'
import { Plus, X } from 'lucide-react'
import { useNavigationStore } from '../../stores/navigation.ts'
import { useEntityRegistry } from '../../api/registry.ts'
import { useViewConfig, useUpdateViewFilters } from '../../api/views.ts'
import type { FieldDef } from '../../types/api.ts'

const OPERATOR_LABELS: Record<string, string> = {
  equals: 'Equals',
  not_equals: 'Does Not Equal',
  contains: 'Contains',
  not_contains: 'Does Not Contain',
  starts_with: 'Starts With',
  is_empty: 'Is Empty',
  is_not_empty: 'Is Not Empty',
  gt: 'Greater Than',
  lt: 'Less Than',
  gte: '>=',
  lte: '<=',
  is_before: 'Is Before',
  is_after: 'Is After',
}

const OPERATORS_BY_TYPE: Record<string, string[]> = {
  text: ['equals', 'not_equals', 'contains', 'not_contains', 'starts_with', 'is_empty', 'is_not_empty'],
  number: ['equals', 'not_equals', 'gt', 'lt', 'gte', 'lte', 'is_empty', 'is_not_empty'],
  datetime: ['is_before', 'is_after', 'equals', 'is_empty', 'is_not_empty'],
  select: ['equals', 'not_equals', 'is_empty', 'is_not_empty'],
}

const NO_VALUE_OPS = new Set(['is_empty', 'is_not_empty'])

interface FilterRow {
  field_key: string
  operator: string
  value: string
}

export function FilterBuilder({ onClose }: { onClose: () => void }) {
  const activeViewId = useNavigationStore((s) => s.activeViewId)
  const activeEntityType = useNavigationStore((s) => s.activeEntityType)
  const { data: registry } = useEntityRegistry()
  const { data: viewConfig } = useViewConfig(activeViewId)
  const updateFilters = useUpdateViewFilters(activeViewId ?? '')
  const ref = useRef<HTMLDivElement>(null)

  const entityDef = registry?.[activeEntityType]
  const existingFilters = viewConfig?.filters ?? []

  const [filters, setFilters] = useState<FilterRow[]>([])

  useEffect(() => {
    setFilters(
      existingFilters.map((f) => ({
        field_key: f.field_key,
        operator: f.operator,
        value: f.value ?? '',
      })),
    )
  }, [existingFilters.length]) // eslint-disable-line react-hooks/exhaustive-deps

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose])

  if (!entityDef) return null

  const filterableFields = Object.entries(entityDef.fields).filter(
    ([, fd]: [string, FieldDef]) => fd.filterable && fd.type !== 'hidden',
  )

  const addFilter = () => {
    if (filterableFields.length === 0) return
    const [key, fd] = filterableFields[0]
    const ops = OPERATORS_BY_TYPE[fd.type] ?? OPERATORS_BY_TYPE.text
    setFilters([...filters, { field_key: key, operator: ops[0], value: '' }])
  }

  const updateFilter = (idx: number, patch: Partial<FilterRow>) => {
    const next = [...filters]
    next[idx] = { ...next[idx], ...patch }
    // Reset value when changing to no-value op
    if (patch.operator && NO_VALUE_OPS.has(patch.operator)) {
      next[idx].value = ''
    }
    // Reset operator when field changes to different type
    if (patch.field_key) {
      const fd = entityDef.fields[patch.field_key]
      const ops = OPERATORS_BY_TYPE[fd?.type ?? 'text'] ?? OPERATORS_BY_TYPE.text
      if (!ops.includes(next[idx].operator)) {
        next[idx].operator = ops[0]
      }
    }
    setFilters(next)
  }

  const removeFilter = (idx: number) => {
    setFilters(filters.filter((_, i) => i !== idx))
  }

  const apply = () => {
    updateFilters.mutate({
      filters: filters.map((f) => ({
        field_key: f.field_key,
        operator: f.operator,
        value: NO_VALUE_OPS.has(f.operator) ? undefined : f.value || undefined,
      })),
    })
    onClose()
  }

  return (
    <div
      ref={ref}
      className="absolute right-0 top-full z-50 mt-1 w-[480px] rounded-lg border border-surface-200 bg-surface-0 shadow-lg"
    >
      <div className="border-b border-surface-200 px-3 py-2 text-xs font-semibold text-surface-500">
        Filters
      </div>

      <div className="max-h-64 overflow-y-auto p-2 space-y-2">
        {filters.length === 0 && (
          <div className="py-3 text-center text-xs text-surface-400">
            No filters applied
          </div>
        )}
        {filters.map((f, idx) => {
          const fd = entityDef.fields[f.field_key]
          const fieldType = fd?.type ?? 'text'
          const ops = OPERATORS_BY_TYPE[fieldType] ?? OPERATORS_BY_TYPE.text
          const isNoValue = NO_VALUE_OPS.has(f.operator)

          return (
            <div key={idx} className="flex items-center gap-1.5">
              {/* Field */}
              <select
                value={f.field_key}
                onChange={(e) => updateFilter(idx, { field_key: e.target.value })}
                className="h-7 w-[130px] rounded border border-surface-200 bg-surface-0 px-1.5 text-xs outline-none"
              >
                {filterableFields.map(([key, fld]) => (
                  <option key={key} value={key}>
                    {(fld as FieldDef).label}
                  </option>
                ))}
              </select>

              {/* Operator */}
              <select
                value={f.operator}
                onChange={(e) => updateFilter(idx, { operator: e.target.value })}
                className="h-7 w-[120px] rounded border border-surface-200 bg-surface-0 px-1.5 text-xs outline-none"
              >
                {ops.map((op) => (
                  <option key={op} value={op}>
                    {OPERATOR_LABELS[op] ?? op}
                  </option>
                ))}
              </select>

              {/* Value */}
              {!isNoValue && (
                fd?.select_options ? (
                  <select
                    value={f.value}
                    onChange={(e) => updateFilter(idx, { value: e.target.value })}
                    className="h-7 flex-1 rounded border border-surface-200 bg-surface-0 px-1.5 text-xs outline-none"
                  >
                    <option value="">--</option>
                    {fd.select_options.map((opt) => (
                      <option key={opt} value={opt}>
                        {opt}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type={fieldType === 'datetime' ? 'date' : 'text'}
                    value={f.value}
                    onChange={(e) => updateFilter(idx, { value: e.target.value })}
                    placeholder="Value..."
                    className="h-7 flex-1 rounded border border-surface-200 bg-surface-0 px-1.5 text-xs outline-none"
                  />
                )
              )}

              {/* Remove */}
              <button
                onClick={() => removeFilter(idx)}
                className="flex h-5 w-5 shrink-0 items-center justify-center rounded text-surface-400 hover:bg-red-100 hover:text-red-500"
              >
                <X size={12} />
              </button>
            </div>
          )
        })}
      </div>

      <div className="flex items-center justify-between border-t border-surface-200 px-3 py-2">
        <button
          onClick={addFilter}
          className="flex items-center gap-1 text-xs text-primary-600 hover:text-primary-700"
        >
          <Plus size={12} />
          Add condition
        </button>
        <button
          onClick={apply}
          className="rounded bg-primary-600 px-3 py-1 text-xs font-medium text-white hover:bg-primary-700"
        >
          Apply
        </button>
      </div>
    </div>
  )
}
