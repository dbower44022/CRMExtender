/**
 * Display profile detection — viewport measurement and tier classification.
 */
import type { DisplayProfile, DisplayTier } from '../types/api.ts'

const ICON_RAIL_WIDTH = 60
const SCROLLBAR_WIDTH = 15
const DIVIDER_WIDTH = 4

const HEADER_HEIGHT = 48
const TOOLBAR_HEIGHT = 40
const COLUMN_HEADER_HEIGHT = 36
const FOOTER_HEIGHT = 32

export function buildDisplayProfile(): DisplayProfile {
  const viewportWidth = window.innerWidth
  const viewportHeight = window.innerHeight
  const devicePixelRatio = window.devicePixelRatio || 1

  const effectiveWidth =
    viewportWidth - ICON_RAIL_WIDTH - SCROLLBAR_WIDTH - DIVIDER_WIDTH

  const effectiveHeight =
    viewportHeight - HEADER_HEIGHT - TOOLBAR_HEIGHT - COLUMN_HEADER_HEIGHT - FOOTER_HEIGHT

  const displayTier = classifyDisplayTier(effectiveWidth)

  return {
    viewportWidth,
    viewportHeight,
    devicePixelRatio,
    effectiveWidth,
    effectiveHeight,
    displayTier,
  }
}

export function classifyDisplayTier(effectiveWidth: number): DisplayTier {
  if (effectiveWidth >= 2400) return 'ultra_wide'
  if (effectiveWidth >= 1920) return 'spacious'
  if (effectiveWidth >= 1440) return 'standard'
  if (effectiveWidth >= 1024) return 'constrained'
  return 'minimal'
}

/**
 * Detect a significant resize (>15% change in effective width).
 */
export function isSignificantResize(
  prev: DisplayProfile,
  curr: DisplayProfile,
): boolean {
  const widthChange = Math.abs(curr.effectiveWidth - prev.effectiveWidth)
  return widthChange / prev.effectiveWidth > 0.15
}
