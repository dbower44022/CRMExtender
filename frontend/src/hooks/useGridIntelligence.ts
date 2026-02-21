/**
 * React hook that orchestrates the Adaptive Grid Intelligence layout engine.
 *
 * Computes optimal column widths, alignment, and demotion based on
 * actual data content, display characteristics, and user overrides.
 */
import { useMemo, useEffect, useRef, useCallback } from 'react'
import type { CellAlignment, ComputedLayout, ViewColumn, View } from '../types/api.ts'
import type { EntityDef } from '../types/api.ts'
import { useLayoutOverrides, useUpsertLayoutOverride } from '../api/layoutOverrides.ts'
import { useGridIntelligenceStore } from '../stores/gridIntelligence.ts'
import { computeLayout } from '../lib/layoutEngine.ts'
import { buildDisplayProfile, isSignificantResize } from '../lib/displayProfile.ts'

interface UseGridIntelligenceOptions {
  rows: Record<string, unknown>[]
  viewColumns: ViewColumn[]
  entityDef: EntityDef | undefined
  viewConfig: View | undefined
}

export function useGridIntelligence({
  rows,
  viewColumns,
  entityDef,
  viewConfig,
}: UseGridIntelligenceOptions): ComputedLayout | null {
  const viewId = viewConfig?.id ?? null
  const { data: overrides } = useLayoutOverrides(viewId)
  const setComputedLayout = useGridIntelligenceStore((s) => s.setComputedLayout)
  const setSaveAlignmentOverride = useGridIntelligenceStore((s) => s.setSaveAlignmentOverride)
  const upsertOverride = useUpsertLayoutOverride(viewId ?? '')

  // Track display profile for resize detection
  const lastProfileRef = useRef(buildDisplayProfile())
  const isAutoConfiguringRef = useRef(false)

  // Use first page rows only (stable ref — don't recompute on infinite scroll)
  const firstPageRows = useMemo(() => {
    return rows.slice(0, 50)
  }, [rows.length <= 50 ? rows : rows.slice(0, 50)]) // eslint-disable-line react-hooks/exhaustive-deps

  // Compute layout
  const layout = useMemo<ComputedLayout | null>(() => {
    if (!entityDef || !viewConfig || viewColumns.length === 0) return null

    const autoSizing = viewConfig.column_auto_sizing !== 0
    const demotion = viewConfig.column_demotion !== 0

    try {
      isAutoConfiguringRef.current = true
      const result = computeLayout({
        rows: firstPageRows,
        viewColumns,
        entityDef,
        primaryIdentifierField: viewConfig.primary_identifier_field,
        columnAutoSizing: autoSizing,
        columnDemotion: demotion,
        overrides: overrides ?? [],
      })
      return result
    } finally {
      isAutoConfiguringRef.current = false
    }
  }, [firstPageRows, viewColumns, entityDef, viewConfig, overrides])

  // Write to store so GridToolbar can access it
  useEffect(() => {
    setComputedLayout(layout)
    return () => setComputedLayout(null)
  }, [layout, setComputedLayout])

  // Significant resize detection
  const handleResize = useCallback(() => {
    const current = buildDisplayProfile()
    if (isSignificantResize(lastProfileRef.current, current)) {
      lastProfileRef.current = current
      // Trigger recompute by invalidating — the layout useMemo
      // will pick up the new profile on next render
    }
  }, [])

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>
    const debouncedResize = () => {
      clearTimeout(timer)
      timer = setTimeout(handleResize, 250)
    }
    window.addEventListener('resize', debouncedResize)
    return () => {
      window.removeEventListener('resize', debouncedResize)
      clearTimeout(timer)
    }
  }, [handleResize])

  // Save column overrides on user-initiated resize (debounced)
  const saveTimerRef = useRef<ReturnType<typeof setTimeout>>(undefined)

  const saveColumnOverride = useCallback(
    (fieldKey: string, widthPct: number) => {
      if (!viewId || isAutoConfiguringRef.current) return

      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
      saveTimerRef.current = setTimeout(() => {
        const profile = buildDisplayProfile()
        const existingOverride = overrides?.find(
          (o) => o.display_tier === profile.displayTier,
        )
        const existing = existingOverride?.column_overrides ?? {}
        upsertOverride.mutate({
          displayTier: profile.displayTier,
          column_overrides: {
            ...existing,
            [fieldKey]: { width_pct: widthPct },
          },
        })
      }, 500)
    },
    [viewId, overrides, upsertOverride],
  )

  // Expose saveColumnOverride via ref so DataGrid can call it
  const saveRef = useRef(saveColumnOverride)
  saveRef.current = saveColumnOverride

  // Save alignment override — merges into existing column_overrides
  const saveAlignmentOverride = useCallback(
    (fieldKey: string, alignment: CellAlignment | null) => {
      if (!viewId) return

      const profile = buildDisplayProfile()
      const existingOverride = overrides?.find(
        (o) => o.display_tier === profile.displayTier,
      )
      const existing = existingOverride?.column_overrides ?? {}
      const fieldOverride = (existing[fieldKey] as Record<string, unknown>) ?? {}

      let updatedFieldOverride: Record<string, unknown>
      if (alignment === null) {
        // Remove alignment key (revert to auto), preserve other keys
        const { alignment: _, ...rest } = fieldOverride
        updatedFieldOverride = rest
      } else {
        updatedFieldOverride = { ...fieldOverride, alignment }
      }

      upsertOverride.mutate({
        displayTier: profile.displayTier,
        column_overrides: {
          ...existing,
          [fieldKey]: updatedFieldOverride,
        },
      })
    },
    [viewId, overrides, upsertOverride],
  )

  // Write saveAlignmentOverride to store so ColumnPicker can access it
  useEffect(() => {
    setSaveAlignmentOverride(saveAlignmentOverride)
    return () => setSaveAlignmentOverride(null)
  }, [saveAlignmentOverride, setSaveAlignmentOverride])

  return layout
}
