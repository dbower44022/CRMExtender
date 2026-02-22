/**
 * Zustand store for grid display settings with localStorage persistence.
 *
 * Provides user-level defaults (tier 2 in the cascade). Per-view density
 * overrides (tier 1) are stored via the layout overrides API.
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type Density = 'compact' | 'standard' | 'comfortable'
export type FontSize = 'small' | 'medium' | 'large'
export type Gridlines = 'both' | 'horizontal' | 'vertical' | 'none'

export const DENSITY_ROW_HEIGHT = { compact: 34, standard: 42, comfortable: 50 } as const
export const DENSITY_HEADER_HEIGHT = { compact: 30, standard: 36, comfortable: 42 } as const
export const FONT_SIZE_CLASS = { small: 'text-xs', medium: 'text-[13px]', large: 'text-sm' } as const

interface GridDisplayState {
  density: Density
  fontSize: FontSize
  alternatingRows: boolean
  gridlines: Gridlines
  rowHover: boolean

  setDensity: (d: Density) => void
  setFontSize: (f: FontSize) => void
  setAlternatingRows: (v: boolean) => void
  setGridlines: (g: Gridlines) => void
  setRowHover: (v: boolean) => void
}

export const useGridDisplayStore = create<GridDisplayState>()(
  persist(
    (set) => ({
      density: 'compact',
      fontSize: 'small',
      alternatingRows: true,
      gridlines: 'horizontal',
      rowHover: true,

      setDensity: (density) => set({ density }),
      setFontSize: (fontSize) => set({ fontSize }),
      setAlternatingRows: (alternatingRows) => set({ alternatingRows }),
      setGridlines: (gridlines) => set({ gridlines }),
      setRowHover: (rowHover) => set({ rowHover }),
    }),
    { name: 'crm-grid-display' },
  ),
)
