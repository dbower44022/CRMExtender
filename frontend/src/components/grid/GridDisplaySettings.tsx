import { useRef, useEffect } from 'react'
import { RotateCcw } from 'lucide-react'
import { useNavigationStore } from '../../stores/navigation.ts'
import {
  useGridDisplayStore,
  DENSITY_ROW_HEIGHT,
  type Density,
  type FontSize,
  type Gridlines,
} from '../../stores/gridDisplay.ts'
import { useLayoutOverrides, useUpsertLayoutOverride } from '../../api/layoutOverrides.ts'
import { buildDisplayProfile } from '../../lib/displayProfile.ts'

export function GridDisplaySettings({ onClose }: { onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null)
  const activeViewId = useNavigationStore((s) => s.activeViewId)

  const density = useGridDisplayStore((s) => s.density)
  const fontSize = useGridDisplayStore((s) => s.fontSize)
  const alternatingRows = useGridDisplayStore((s) => s.alternatingRows)
  const gridlines = useGridDisplayStore((s) => s.gridlines)
  const rowHover = useGridDisplayStore((s) => s.rowHover)
  const setDensity = useGridDisplayStore((s) => s.setDensity)
  const setFontSize = useGridDisplayStore((s) => s.setFontSize)
  const setAlternatingRows = useGridDisplayStore((s) => s.setAlternatingRows)
  const setGridlines = useGridDisplayStore((s) => s.setGridlines)
  const setRowHover = useGridDisplayStore((s) => s.setRowHover)

  const { data: overrides } = useLayoutOverrides(activeViewId)
  const upsertOverride = useUpsertLayoutOverride(activeViewId ?? '')

  // Determine if the current view has a density override for this tier
  const currentTier = buildDisplayProfile().displayTier
  const tierOverride = overrides?.find((o) => o.display_tier === currentTier)
  const viewDensity = tierOverride?.density as Density | null | undefined

  const handleDensityChange = (d: Density) => {
    setDensity(d)
    // Also persist to per-view layout override
    if (activeViewId) {
      upsertOverride.mutate({
        displayTier: currentTier,
        density: d,
      })
    }
  }

  const resetViewOverride = () => {
    if (activeViewId) {
      upsertOverride.mutate({
        displayTier: currentTier,
        density: null,
      })
    }
  }

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

  const densityOptions: { value: Density; label: string }[] = [
    { value: 'compact', label: 'Compact' },
    { value: 'standard', label: 'Standard' },
    { value: 'comfortable', label: 'Comfortable' },
  ]

  const fontOptions: { value: FontSize; label: string }[] = [
    { value: 'small', label: 'S' },
    { value: 'medium', label: 'M' },
    { value: 'large', label: 'L' },
  ]

  const gridlineOptions: { value: Gridlines; label: string }[] = [
    { value: 'both', label: 'Both' },
    { value: 'horizontal', label: 'H' },
    { value: 'vertical', label: 'V' },
    { value: 'none', label: 'None' },
  ]

  return (
    <div
      ref={ref}
      className="absolute left-0 top-full z-50 mt-1 w-72 rounded-lg border border-surface-200 bg-surface-0 shadow-lg"
    >
      <div className="border-b border-surface-200 px-3 py-2 text-xs font-semibold text-surface-500">
        Display Settings
      </div>

      <div className="space-y-3 p-3">
        {/* Row Density */}
        <SettingRow
          label="Row Density"
          hint={viewDensity ? '(view)' : '(default)'}
        >
          <SegmentedControl
            options={densityOptions}
            value={density}
            onChange={handleDensityChange}
          />
        </SettingRow>

        {/* Font Size */}
        <SettingRow label="Font Size">
          <SegmentedControl
            options={fontOptions}
            value={fontSize}
            onChange={setFontSize}
          />
        </SettingRow>

        {/* Alternating Rows */}
        <SettingRow label="Alternating Rows">
          <ToggleButton value={alternatingRows} onChange={setAlternatingRows} />
        </SettingRow>

        {/* Gridlines */}
        <SettingRow label="Gridlines">
          <SegmentedControl
            options={gridlineOptions}
            value={gridlines}
            onChange={setGridlines}
          />
        </SettingRow>

        {/* Row Hover */}
        <SettingRow label="Row Hover">
          <ToggleButton value={rowHover} onChange={setRowHover} />
        </SettingRow>
      </div>

      {/* Reset view override */}
      {viewDensity && (
        <div className="border-t border-surface-200 px-3 py-2">
          <button
            onClick={resetViewOverride}
            className="flex items-center gap-1.5 text-xs text-primary-600 hover:text-primary-700"
          >
            <RotateCcw size={12} />
            Reset View Override
          </button>
        </div>
      )}
    </div>
  )
}

function SettingRow({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-xs text-surface-600">
        {label}
        {hint && <span className="ml-1 text-surface-400">{hint}</span>}
      </span>
      {children}
    </div>
  )
}

function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[]
  value: T
  onChange: (v: T) => void
}) {
  return (
    <div className="flex rounded border border-surface-200">
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`px-2 py-1 text-[11px] font-medium transition-colors ${
            opt.value === value
              ? 'bg-primary-600 text-white'
              : 'text-surface-500 hover:bg-surface-50'
          } ${
            opt.value === options[0].value ? 'rounded-l' : ''
          } ${
            opt.value === options[options.length - 1].value ? 'rounded-r' : ''
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

function ToggleButton({
  value,
  onChange,
}: {
  value: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <button
      onClick={() => onChange(!value)}
      className={`relative h-5 w-9 rounded-full transition-colors ${
        value ? 'bg-primary-600' : 'bg-surface-300'
      }`}
    >
      <span
        className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${
          value ? 'translate-x-4' : 'translate-x-0.5'
        }`}
      />
    </button>
  )
}
