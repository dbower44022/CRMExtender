import { useState, useRef, useEffect } from 'react'
import { ChevronUp, ChevronDown, X, Plus, AlignLeft, AlignCenter, AlignRight } from 'lucide-react'
import { useNavigationStore } from '../../stores/navigation.ts'
import { useEntityRegistry } from '../../api/registry.ts'
import { useViewConfig, useUpdateViewColumns } from '../../api/views.ts'
import { useLayoutOverrides } from '../../api/layoutOverrides.ts'
import { useGridIntelligenceStore } from '../../stores/gridIntelligence.ts'
import { buildDisplayProfile } from '../../lib/displayProfile.ts'
import type { ViewColumn, FieldDef, CellAlignment } from '../../types/api.ts'

export function ColumnPicker({ onClose }: { onClose: () => void }) {
  const activeViewId = useNavigationStore((s) => s.activeViewId)
  const activeEntityType = useNavigationStore((s) => s.activeEntityType)
  const { data: registry } = useEntityRegistry()
  const { data: viewConfig } = useViewConfig(activeViewId)
  const updateColumns = useUpdateViewColumns(activeViewId ?? '')
  const ref = useRef<HTMLDivElement>(null)

  const entityDef = registry?.[activeEntityType]
  const viewColumns = viewConfig?.columns ?? []

  // Layout overrides + computed layout for alignment state
  const { data: overrides } = useLayoutOverrides(activeViewId)
  const computedLayout = useGridIntelligenceStore((s) => s.computedLayout)
  const saveAlignmentOverride = useGridIntelligenceStore((s) => s.saveAlignmentOverride)

  // Determine current alignment override tier
  const currentTierOverrides = (() => {
    if (!overrides) return {} as Record<string, Record<string, unknown>>
    const tier = buildDisplayProfile().displayTier
    const match = overrides.find((o) => o.display_tier === tier)
    return (match?.column_overrides ?? {}) as Record<string, Record<string, unknown>>
  })()

  // Get effective alignment for a column: override > computed > 'left'
  const getAlignment = (fieldKey: string): CellAlignment => {
    const overrideAlign = currentTierOverrides[fieldKey]?.alignment as CellAlignment | undefined
    if (overrideAlign) return overrideAlign
    const col = computedLayout?.columns.find((c) => c.fieldKey === fieldKey)
    return col?.alignment ?? 'left'
  }

  // Whether this column has a user-set alignment override
  const hasAlignmentOverride = (fieldKey: string): boolean => {
    return !!currentTierOverrides[fieldKey]?.alignment
  }

  const handleAlignmentClick = (fieldKey: string, alignment: CellAlignment) => {
    if (!saveAlignmentOverride) return
    const current = getAlignment(fieldKey)
    const isOverridden = hasAlignmentOverride(fieldKey)
    // Clicking the active alignment when it's user-set reverts to auto
    if (alignment === current && isOverridden) {
      saveAlignmentOverride(fieldKey, null)
    } else {
      saveAlignmentOverride(fieldKey, alignment)
    }
  }

  // Local state for ordering
  const [columns, setColumns] = useState<
    { key: string; label?: string; width?: number }[]
  >([])

  useEffect(() => {
    if (viewColumns.length > 0 && entityDef) {
      setColumns(
        viewColumns
          .filter((vc: ViewColumn) => {
            const fd = entityDef.fields[vc.field_key]
            return fd && fd.type !== 'hidden'
          })
          .map((vc: ViewColumn) => ({
            key: vc.field_key,
            label: vc.label_override || undefined,
            width: vc.width_px || undefined,
          })),
      )
    }
  }, [viewColumns, entityDef])

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

  const selectedKeys = new Set(columns.map((c) => c.key))
  const availableFields = Object.entries(entityDef.fields)
    .filter(
      ([key, fd]: [string, FieldDef]) =>
        fd.type !== 'hidden' && !selectedKeys.has(key),
    )
    .sort(([, a], [, b]) => a.label.localeCompare(b.label))

  const moveUp = (idx: number) => {
    if (idx === 0) return
    const next = [...columns]
    ;[next[idx - 1], next[idx]] = [next[idx], next[idx - 1]]
    setColumns(next)
  }

  const moveDown = (idx: number) => {
    if (idx === columns.length - 1) return
    const next = [...columns]
    ;[next[idx], next[idx + 1]] = [next[idx + 1], next[idx]]
    setColumns(next)
  }

  const removeCol = (idx: number) => {
    setColumns(columns.filter((_, i) => i !== idx))
  }

  const addCol = (key: string) => {
    setColumns([...columns, { key }])
  }

  const apply = () => {
    updateColumns.mutate({ columns })
    onClose()
  }

  return (
    <div
      ref={ref}
      className="absolute left-0 top-full z-50 mt-1 w-80 rounded-lg border border-surface-200 bg-surface-0 shadow-lg"
    >
      <div className="border-b border-surface-200 px-3 py-2 text-xs font-semibold text-surface-500">
        Columns
      </div>

      <div className="max-h-64 overflow-y-auto p-2">
        {columns.map((col, idx) => {
          const fd = entityDef.fields[col.key]
          const activeAlign = getAlignment(col.key)
          const isOverridden = hasAlignmentOverride(col.key)
          return (
            <div
              key={col.key}
              className="flex items-center gap-1 rounded px-1.5 py-1 text-sm text-surface-700 hover:bg-surface-50"
            >
              <span className="min-w-0 flex-1 truncate">
                {col.label || fd?.label || col.key}
              </span>
              <AlignmentToggle
                active={activeAlign}
                isOverridden={isOverridden}
                onChange={(a) => handleAlignmentClick(col.key, a)}
              />
              <button
                onClick={() => moveUp(idx)}
                disabled={idx === 0}
                className="flex h-5 w-5 items-center justify-center rounded text-surface-400 hover:bg-surface-200 disabled:opacity-30"
              >
                <ChevronUp size={12} />
              </button>
              <button
                onClick={() => moveDown(idx)}
                disabled={idx === columns.length - 1}
                className="flex h-5 w-5 items-center justify-center rounded text-surface-400 hover:bg-surface-200 disabled:opacity-30"
              >
                <ChevronDown size={12} />
              </button>
              <button
                onClick={() => removeCol(idx)}
                className="flex h-5 w-5 items-center justify-center rounded text-surface-400 hover:bg-red-100 hover:text-red-500"
              >
                <X size={12} />
              </button>
            </div>
          )
        })}
      </div>

      {availableFields.length > 0 && (
        <div className="border-t border-surface-200 p-2">
          <AddColumnDropdown fields={availableFields} onAdd={addCol} />
        </div>
      )}

      <div className="flex justify-end border-t border-surface-200 px-3 py-2">
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

function AlignmentToggle({
  active,
  isOverridden,
  onChange,
}: {
  active: CellAlignment
  isOverridden: boolean
  onChange: (alignment: CellAlignment) => void
}) {
  const buttons: { align: CellAlignment; Icon: typeof AlignLeft }[] = [
    { align: 'left', Icon: AlignLeft },
    { align: 'center', Icon: AlignCenter },
    { align: 'right', Icon: AlignRight },
  ]
  return (
    <div className="flex gap-px rounded border border-surface-200">
      {buttons.map(({ align, Icon }) => {
        const isActive = align === active
        return (
          <button
            key={align}
            onClick={() => onChange(align)}
            title={
              isActive && isOverridden
                ? `${align} (click to revert to auto)`
                : isActive
                  ? `${align} (auto)`
                  : align
            }
            className={`flex h-5 w-5 items-center justify-center ${
              isActive
                ? isOverridden
                  ? 'bg-primary-600 text-white'
                  : 'bg-surface-200 text-surface-700'
                : 'text-surface-400 hover:bg-surface-100'
            }`}
          >
            <Icon size={10} />
          </button>
        )
      })}
    </div>
  )
}

function AddColumnDropdown({
  fields,
  onAdd,
}: {
  fields: [string, FieldDef][]
  onAdd: (key: string) => void
}) {
  const [open, setOpen] = useState(false)

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-1 text-xs text-primary-600 hover:text-primary-700"
      >
        <Plus size={12} />
        Add column
      </button>
    )
  }

  return (
    <div className="max-h-32 overflow-y-auto">
      {fields.map(([key, fd]) => (
        <button
          key={key}
          onClick={() => {
            onAdd(key)
            setOpen(false)
          }}
          className="flex w-full items-center gap-2 rounded px-2 py-1 text-left text-xs text-surface-600 hover:bg-surface-100"
        >
          <Plus size={10} />
          {fd.label}
        </button>
      ))}
    </div>
  )
}
