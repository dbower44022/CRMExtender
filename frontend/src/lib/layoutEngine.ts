/**
 * Layout engine orchestrator — full auto-configuration sequence.
 *
 * Composes display profile, content analysis, priority, alignment,
 * demotion, and width allocation into a single ComputedLayout.
 */
import type {
  CellAlignment,
  ComputedColumn,
  ComputedLayout,
  DisplayProfile,
  LayoutOverride,
  ViewColumn,
} from '../types/api.ts'
import type { EntityDef, FieldDef } from '../types/api.ts'

import { buildDisplayProfile } from './displayProfile.ts'
import { analyzeContent } from './contentAnalysis.ts'
import { assignPriority } from './columnPriority.ts'
import { computeAlignment } from './cellAlignment.ts'
import { computeDemotion } from './diversityDemotion.ts'
import { allocateColumnWidths } from './columnAllocation.ts'

interface ComputeLayoutOptions {
  rows: Record<string, unknown>[]
  viewColumns: ViewColumn[]
  entityDef: EntityDef
  primaryIdentifierField?: string | null
  columnAutoSizing?: boolean
  columnDemotion?: boolean
  overrides?: LayoutOverride[]
  displayProfile?: DisplayProfile
}

/**
 * Compute the full auto-configured layout for a grid.
 *
 * This is the main entry point called by useGridIntelligence.
 */
export function computeLayout(options: ComputeLayoutOptions): ComputedLayout {
  const {
    rows,
    viewColumns,
    entityDef,
    primaryIdentifierField,
    columnAutoSizing = true,
    columnDemotion: demotionEnabled = true,
    overrides = [],
    displayProfile: providedProfile,
  } = options

  const displayProfile = providedProfile ?? buildDisplayProfile()

  // Get visible field keys (exclude hidden type fields)
  const visibleColumns = viewColumns.filter((vc) => {
    const fd = entityDef.fields[vc.field_key]
    return fd && fd.type !== 'hidden'
  })

  const fieldKeys = visibleColumns.map((vc) => vc.field_key)

  // If auto-sizing is disabled or no rows, fall back to static widths
  if (!columnAutoSizing || rows.length === 0) {
    const columns: ComputedColumn[] = visibleColumns.map((vc) => ({
      fieldKey: vc.field_key,
      computedWidth: vc.width_px ?? 150,
      alignment: 'left',
      demotionTier: 'normal',
      dominantValue: null,
      priorityClass: 2,
    }))
    return {
      displayProfile,
      columns,
      demotedCount: 0,
      hiddenCount: 0,
    }
  }

  // Find the current-tier override if any
  const currentOverride = overrides.find(
    (o) => o.display_tier === displayProfile.displayTier,
  )
  const colOverrides = currentOverride?.column_overrides ?? {}

  // Step 1: Content analysis
  const metrics = analyzeContent(rows, fieldKeys, entityDef.fields)
  const metricsMap = new Map(metrics.map((m) => [m.fieldKey, m]))

  // Step 2: Determine primary identifier
  const primaryField =
    primaryIdentifierField ??
    fieldKeys.find((fk) => {
      const fd = entityDef.fields[fk]
      return fd?.type === 'text'
    }) ??
    fieldKeys[0]

  // Step 3: Assign priorities
  const priorities = new Map<string, number>()
  for (const fk of fieldKeys) {
    const fd = entityDef.fields[fk]
    const m = metricsMap.get(fk)!
    priorities.set(fk, assignPriority(fk, fd, m, fk === primaryField))
  }

  // Step 4: Compute demotion
  const demotions = new Map<string, ReturnType<typeof computeDemotion>>()
  for (const fk of fieldKeys) {
    const m = metricsMap.get(fk)!
    const priority = priorities.get(fk)!
    const hasOverride = fk in colOverrides
    if (demotionEnabled) {
      demotions.set(fk, computeDemotion(m, priority, hasOverride))
    } else {
      demotions.set(fk, 'normal')
    }
  }

  // Step 5: Allocate widths
  const allocationInput = fieldKeys.map((fk) => {
    const fd = entityDef.fields[fk] as FieldDef
    const m = metricsMap.get(fk)!
    const override = colOverrides[fk] as Record<string, unknown> | undefined
    return {
      fieldKey: fk,
      fieldDef: fd,
      metrics: m,
      priorityClass: priorities.get(fk)!,
      demotionTier: demotions.get(fk)!,
      userOverrideWidthPct: override?.width_pct as number | undefined,
    }
  })

  const allocations = allocateColumnWidths(
    displayProfile.effectiveWidth,
    allocationInput,
  )
  const widthMap = new Map(allocations.map((a) => [a.fieldKey, a.width]))

  // Step 6: Compute alignment (user override takes priority)
  const columns: ComputedColumn[] = fieldKeys.map((fk) => {
    const fd = entityDef.fields[fk] as FieldDef
    const m = metricsMap.get(fk)!
    const width = widthMap.get(fk) ?? 150
    const override = colOverrides[fk] as Record<string, unknown> | undefined
    const alignment = (override?.alignment as CellAlignment | undefined)
      ?? computeAlignment(m, fd, width)
    return {
      fieldKey: fk,
      computedWidth: width,
      alignment,
      demotionTier: demotions.get(fk)!,
      dominantValue: m.dominantValue,
      priorityClass: priorities.get(fk)!,
    }
  })

  const demotedCount = columns.filter(
    (c) => c.demotionTier !== 'normal' && c.demotionTier !== 'hidden',
  ).length
  const hiddenCount = columns.filter((c) => c.demotionTier === 'hidden').length

  return {
    displayProfile,
    columns,
    demotedCount,
    hiddenCount,
  }
}
