/**
 * Value diversity analysis → 4-tier column demotion (PRD §12).
 */
import type { DemotionTier, ColumnMetrics } from '../types/api.ts'

/**
 * Compute the demotion tier for a column based on its diversity score.
 *
 * Tiers:
 * - normal: diversityScore > 0.20
 * - annotated: 0.06–0.20 (reduced width)
 * - collapsed: 0.01–0.05 (narrow indicator)
 * - header_only: 0.0 exactly (uniform — show value in header)
 * - hidden: 0.0 AND nullRatio > 0.9 (effectively empty)
 *
 * Protected columns (primary identifier, user-overridden) return 'normal'.
 */
export function computeDemotion(
  metrics: ColumnMetrics,
  priorityClass: number,
  hasUserOverride: boolean,
): DemotionTier {
  // Protection: primary identifier never demoted
  if (priorityClass === 0) return 'normal'

  // Protection: user-overridden columns never demoted
  if (hasUserOverride) return 'normal'

  const { diversityScore, nullRatio } = metrics

  // Hidden: all same AND mostly null
  if (diversityScore === 0 && nullRatio > 0.9) return 'hidden'

  // Header-only: perfectly uniform (all non-null values identical)
  if (diversityScore === 0) return 'header_only'

  // Collapsed: near-uniform (1-5% distinct)
  if (diversityScore <= 0.05) return 'collapsed'

  // Annotated: low diversity (6-20% distinct)
  if (diversityScore <= 0.20) return 'annotated'

  return 'normal'
}
