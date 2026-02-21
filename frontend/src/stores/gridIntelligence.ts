/**
 * Zustand store for computed grid layout — allows GridToolbar to read
 * computed layout without prop drilling.
 */
import { create } from 'zustand'
import type { CellAlignment, ComputedLayout } from '../types/api.ts'

interface GridIntelligenceState {
  computedLayout: ComputedLayout | null
  setComputedLayout: (layout: ComputedLayout | null) => void
  saveAlignmentOverride: ((fieldKey: string, alignment: CellAlignment | null) => void) | null
  setSaveAlignmentOverride: (fn: ((fieldKey: string, alignment: CellAlignment | null) => void) | null) => void
}

export const useGridIntelligenceStore = create<GridIntelligenceState>()(
  (set) => ({
    computedLayout: null,
    setComputedLayout: (layout) => set({ computedLayout: layout }),
    saveAlignmentOverride: null,
    setSaveAlignmentOverride: (fn) => set({ saveAlignmentOverride: fn }),
  }),
)
