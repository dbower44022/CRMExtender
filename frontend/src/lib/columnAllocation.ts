/**
 * 5-stage column width allocation engine (PRD §10).
 */
import type { ColumnMetrics, DemotionTier } from '../types/api.ts'
import type { FieldDef } from '../types/api.ts'
import { priorityMultiplier } from './columnPriority.ts'

interface ColumnAllocationInput {
  fieldKey: string
  fieldDef: FieldDef
  metrics: ColumnMetrics
  priorityClass: number
  demotionTier: DemotionTier
  userOverrideWidthPct?: number
}

interface ColumnAllocationResult {
  fieldKey: string
  width: number
}

const MIN_WIDTHS: Record<string, number> = {
  primary: 150,
  text: 80,
  number: 50,
  datetime: 100,
  select: 60,
}

const MAX_WIDTH_PCT: Record<string, number> = {
  primary: 0.50,
  text: 0.40,
  number: 0.15,
  datetime: 0.15,
  select: 0.20,
}

function getMinWidth(priorityClass: number, fieldDef: FieldDef): number {
  if (priorityClass === 0) return MIN_WIDTHS.primary
  return MIN_WIDTHS[fieldDef.type] ?? 80
}

function getMaxWidth(priorityClass: number, fieldDef: FieldDef, gridWidth: number): number {
  if (priorityClass === 0) return gridWidth * MAX_WIDTH_PCT.primary
  const pct = MAX_WIDTH_PCT[fieldDef.type] ?? 0.40
  return gridWidth * pct
}

/**
 * Allocate column widths within the available grid width.
 *
 * Stages:
 * 1. Fixed-width columns (none in current schema)
 * 2. User override columns (proportional percentage)
 * 3. Demoted columns (minimal width)
 * 4. Natural-width columns (P90 fits)
 * 5. Weighted distribution of remaining space
 */
export function allocateColumnWidths(
  gridWidth: number,
  columns: ColumnAllocationInput[],
): ColumnAllocationResult[] {
  if (gridWidth <= 0 || columns.length === 0) {
    return columns.map((c) => ({ fieldKey: c.fieldKey, width: 150 }))
  }

  const allocated = new Map<string, number>()
  let remaining = gridWidth

  // Stage 1: Fixed-width columns (currently none)

  // Stage 2: User override columns
  for (const col of columns) {
    if (col.userOverrideWidthPct != null && col.demotionTier === 'normal') {
      const w = Math.round(gridWidth * (col.userOverrideWidthPct / 100))
      const clamped = Math.max(
        getMinWidth(col.priorityClass, col.fieldDef),
        Math.min(w, getMaxWidth(col.priorityClass, col.fieldDef, gridWidth)),
      )
      allocated.set(col.fieldKey, clamped)
      remaining -= clamped
    }
  }

  // Stage 3: Demoted columns
  for (const col of columns) {
    if (allocated.has(col.fieldKey)) continue
    if (col.demotionTier === 'hidden') {
      allocated.set(col.fieldKey, 0)
    } else if (col.demotionTier === 'header_only') {
      allocated.set(col.fieldKey, 70)
      remaining -= 70
    } else if (col.demotionTier === 'collapsed') {
      allocated.set(col.fieldKey, 80)
      remaining -= 80
    }
  }

  // Stage 4: Natural-width columns (P90 fits within 200px)
  for (const col of columns) {
    if (allocated.has(col.fieldKey)) continue
    if (col.metrics.p90ContentWidth > 0 && col.metrics.p90ContentWidth <= 200) {
      const w = Math.max(
        getMinWidth(col.priorityClass, col.fieldDef),
        Math.min(col.metrics.p90ContentWidth, 200),
      )
      allocated.set(col.fieldKey, w)
      remaining -= w
    }
  }

  // Stage 5: Weighted distribution of remaining space
  const unallocated = columns.filter((c) => !allocated.has(c.fieldKey))
  if (unallocated.length > 0 && remaining > 0) {
    const totalWeight = unallocated.reduce((sum, col) => {
      const multiplier = priorityMultiplier(col.priorityClass)
      const contentNeed =
        col.metrics.p90ContentWidth > 0
          ? col.metrics.p90ContentWidth
          : 150
      return sum + multiplier * contentNeed
    }, 0)

    for (const col of unallocated) {
      const multiplier = priorityMultiplier(col.priorityClass)
      const contentNeed =
        col.metrics.p90ContentWidth > 0
          ? col.metrics.p90ContentWidth
          : 150
      const proportion = (multiplier * contentNeed) / totalWeight
      const w = Math.round(remaining * proportion)
      const clamped = Math.max(
        getMinWidth(col.priorityClass, col.fieldDef),
        Math.min(w, getMaxWidth(col.priorityClass, col.fieldDef, gridWidth)),
      )
      allocated.set(col.fieldKey, clamped)
    }
  }

  // Fallback: any still-unallocated column gets 150px
  for (const col of columns) {
    if (!allocated.has(col.fieldKey)) {
      allocated.set(col.fieldKey, 150)
    }
  }

  return columns.map((c) => ({
    fieldKey: c.fieldKey,
    width: allocated.get(c.fieldKey) ?? 150,
  }))
}
