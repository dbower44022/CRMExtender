/**
 * Content analysis engine — Canvas.measureText() sampling of loaded rows.
 */
import type { ColumnMetrics } from '../types/api.ts'
import type { FieldDef } from '../types/api.ts'

const GRID_FONT = '14px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
const CELL_PADDING = 24 // 12px each side (px-3)

let _ctx: CanvasRenderingContext2D | null = null

function getContext(): CanvasRenderingContext2D {
  if (!_ctx) {
    const canvas = document.createElement('canvas')
    _ctx = canvas.getContext('2d')!
    _ctx.font = GRID_FONT
  }
  return _ctx
}

function measureText(text: string): number {
  const ctx = getContext()
  return ctx.measureText(text).width + CELL_PADDING
}

function percentile(sorted: number[], p: number): number {
  if (sorted.length === 0) return 0
  const idx = Math.ceil((p / 100) * sorted.length) - 1
  return sorted[Math.max(0, idx)]
}

/**
 * Analyze content metrics for visible columns on the first page of rows.
 */
export function analyzeContent(
  rows: Record<string, unknown>[],
  fieldKeys: string[],
  fieldDefs: Record<string, FieldDef>,
): ColumnMetrics[] {
  if (rows.length === 0) {
    return fieldKeys.map((fieldKey) => ({
      fieldKey,
      maxContentWidth: 0,
      medianContentWidth: 0,
      p90ContentWidth: 0,
      minContentWidth: 0,
      diversityScore: 0,
      nullRatio: 1,
      dominantValue: null,
      digitCountRange: null,
    }))
  }

  // Sample up to 50 rows
  const sample = rows.slice(0, 50)

  return fieldKeys.map((fieldKey) => {
    const values: string[] = []
    const widths: number[] = []
    let nullCount = 0
    const valueCounts = new Map<string, number>()
    let minDigits = Infinity
    let maxDigits = -Infinity
    const fd = fieldDefs[fieldKey]
    const isNumeric = fd?.type === 'number'

    for (const row of sample) {
      const raw = row[fieldKey]
      if (raw == null || raw === '') {
        nullCount++
        continue
      }
      const str = String(raw)
      values.push(str)
      widths.push(measureText(str))
      valueCounts.set(str, (valueCounts.get(str) || 0) + 1)

      if (isNumeric) {
        const digits = str.replace(/[^0-9.,-]/g, '').length
        if (digits < minDigits) minDigits = digits
        if (digits > maxDigits) maxDigits = digits
      }
    }

    const sortedWidths = [...widths].sort((a, b) => a - b)
    const nonNullCount = values.length
    const distinctCount = valueCounts.size
    const diversityScore =
      nonNullCount > 0 ? distinctCount / nonNullCount : 0
    const nullRatio = nullCount / sample.length

    // Find dominant value if diversity < 0.1
    let dominantValue: string | null = null
    if (diversityScore < 0.1 && valueCounts.size > 0) {
      let maxCount = 0
      for (const [val, count] of valueCounts) {
        if (count > maxCount) {
          maxCount = count
          dominantValue = val
        }
      }
    }

    return {
      fieldKey,
      maxContentWidth: sortedWidths.length > 0 ? sortedWidths[sortedWidths.length - 1] : 0,
      medianContentWidth: percentile(sortedWidths, 50),
      p90ContentWidth: percentile(sortedWidths, 90),
      minContentWidth: sortedWidths.length > 0 ? sortedWidths[0] : 0,
      diversityScore,
      nullRatio,
      dominantValue,
      digitCountRange:
        isNumeric && minDigits !== Infinity
          ? [minDigits, maxDigits]
          : null,
    }
  })
}
