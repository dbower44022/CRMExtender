/**
 * Column priority assignment — P0 (primary identifier) through P7 (utility).
 *
 * Priority classes influence width allocation weight and demotion protection.
 */
import type { ColumnMetrics } from '../types/api.ts'
import type { FieldDef } from '../types/api.ts'

// P0 = Primary identifier (Name, Subject) — highest priority
// P1 = High-value differentiating text
// P2 = Standard columns
// P3 = Numeric/date columns
// P4 = Status/categorical columns
// P5 = Low-diversity columns
// P6 = Nearly empty columns
// P7 = Utility/hidden columns

export function assignPriority(
  _fieldKey: string,
  fieldDef: FieldDef,
  metrics: ColumnMetrics,
  isPrimaryIdentifier: boolean,
): number {
  // P0: Primary identifier
  if (isPrimaryIdentifier) return 0

  // P7: Hidden fields
  if (fieldDef.type === 'hidden') return 7

  // P6: Mostly null (>90%)
  if (metrics.nullRatio > 0.9) return 6

  // P5: Low diversity (uniform-ish values)
  if (metrics.diversityScore < 0.1 && metrics.diversityScore >= 0) return 5

  // P4: Status/select fields
  if (fieldDef.type === 'select') return 4

  // P3: Numeric and datetime
  if (fieldDef.type === 'number' || fieldDef.type === 'datetime') return 3

  // P1: Text with high diversity
  if (fieldDef.type === 'text' && metrics.diversityScore > 0.5) return 1

  // P2: Everything else
  return 2
}

/**
 * Get the weight multiplier for width allocation from priority class.
 */
export function priorityMultiplier(priorityClass: number): number {
  switch (priorityClass) {
    case 0: return 3.0   // Primary identifier
    case 1: return 2.0   // High-value differentiating
    case 2: return 1.0   // Standard
    case 3: return 1.0   // Numeric/date
    case 4: return 0.8   // Categorical
    case 5: return 0.5   // Low diversity
    case 6: return 0.3   // Nearly empty
    case 7: return 0     // Hidden
    default: return 1.0
  }
}
