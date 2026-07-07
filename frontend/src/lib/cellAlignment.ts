/**
 * Content-aware cell alignment — 5-rule decision tree (PRD §11).
 */
import type { CellAlignment, ColumnMetrics } from '../types/api.ts'
import type { FieldDef } from '../types/api.ts'

/**
 * Compute the optimal cell alignment for a column based on its content.
 *
 * Rules evaluated in order — first match wins:
 * 1. Numeric alignment by digit range
 * 2. Temporal alignment by format
 * 3. Categorical alignment (select, hidden)
 * 4. Text alignment (compact vs wide)
 */
export function computeAlignment(
  metrics: ColumnMetrics,
  fieldDef: FieldDef,
  _columnWidth: number,
): CellAlignment {
  // Rule 1: Numeric
  if (fieldDef.type === 'number' && metrics.digitCountRange) {
    const [, maxDigits] = metrics.digitCountRange
    // Single-digit or 1-2 digits → center
    if (maxDigits <= 2) return 'center'
    // 3+ digits or decimals → right
    return 'right'
  }

  // Rule 2: Temporal (datetime fields)
  if (fieldDef.type === 'datetime') {
    // Compressed format (<10 chars median) → center; else left
    if (metrics.medianContentWidth < 100) return 'center'
    return 'left'
  }

  // Rule 3: Categorical
  if (fieldDef.type === 'select') {
    // Short select values (all ≤12 chars → median width small) → center
    if (metrics.maxContentWidth <= 120) return 'center'
    return 'left'
  }

  // Rule 4/5: Text is always left-aligned — identity fields (names,
  // subjects, emails) must share a common left edge for scanning
  // (PRD §11.2 Rule 5, revised 2026-07-07)
  return 'left'
}
