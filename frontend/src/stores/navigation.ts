import { create } from 'zustand'
import type { QuickFilter } from '../types/api.ts'

interface NavigationState {
  activeEntityType: string
  activeViewId: string | null
  selectedRowId: string | null
  selectedRowIndex: number
  selectedRowIds: Set<string>
  loadedRowCount: number
  focusAnchorIndex: number
  focusedColumn: number
  sort: string | null
  sortDirection: 'asc' | 'desc'
  search: string
  quickFilters: QuickFilter[]
  pendingNavigation: { entityType: string; entityId: string } | null

  setActiveEntityType: (entityType: string) => void
  setActiveViewId: (viewId: string | null) => void
  setSelectedRow: (id: string | null, index: number) => void
  toggleRowSelection: (id: string) => void
  selectAllRows: (ids: string[]) => void
  deselectAllRows: () => void
  selectRange: (fromIndex: number, toIndex: number, rows: Record<string, unknown>[]) => void
  setLoadedRowCount: (count: number) => void
  setFocusedColumn: (col: number) => void
  setSort: (field: string, direction: 'asc' | 'desc') => void
  clearSort: () => void
  setSearch: (search: string) => void
  toggleQuickFilter: (filter: QuickFilter) => void
  setPendingNavigation: (nav: { entityType: string; entityId: string } | null) => void
  reset: () => void
}

const DEFAULTS = {
  activeEntityType: 'contact',
  activeViewId: null as string | null,
  selectedRowId: null as string | null,
  selectedRowIndex: -1,
  selectedRowIds: new Set<string>(),
  loadedRowCount: 0,
  focusAnchorIndex: -1,
  focusedColumn: 0,
  sort: null as string | null,
  sortDirection: 'asc' as const,
  search: '',
  quickFilters: [] as QuickFilter[],
  pendingNavigation: null as { entityType: string; entityId: string } | null,
}

export const useNavigationStore = create<NavigationState>()((set) => ({
  ...DEFAULTS,

  setActiveEntityType: (entityType) =>
    set({
      activeEntityType: entityType,
      activeViewId: null,
      selectedRowId: null,
      selectedRowIndex: -1,
      selectedRowIds: new Set<string>(),
      focusAnchorIndex: -1,
      focusedColumn: 0,
      sort: null,
      sortDirection: 'asc',
      search: '',
      quickFilters: [],
    }),

  setActiveViewId: (viewId) =>
    set({
      activeViewId: viewId,
      selectedRowId: null,
      selectedRowIndex: -1,
      selectedRowIds: new Set<string>(),
      focusAnchorIndex: -1,
      focusedColumn: 0,
      quickFilters: [],
    }),

  setSelectedRow: (id, index) =>
    set({ selectedRowId: id, selectedRowIndex: index, focusAnchorIndex: index }),

  toggleRowSelection: (id) =>
    set((state) => {
      const next = new Set(state.selectedRowIds)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return { selectedRowIds: next }
    }),

  selectAllRows: (ids) =>
    set({ selectedRowIds: new Set(ids) }),

  deselectAllRows: () =>
    set({ selectedRowIds: new Set<string>() }),

  selectRange: (fromIndex, toIndex, rows) =>
    set((state) => {
      const lo = Math.min(fromIndex, toIndex)
      const hi = Math.max(fromIndex, toIndex)
      const next = new Set(state.selectedRowIds)
      for (let i = lo; i <= hi; i++) {
        const row = rows[i]
        if (row) next.add(String(row.id))
      }
      return { selectedRowIds: next }
    }),

  setLoadedRowCount: (count) =>
    set({ loadedRowCount: count }),

  setFocusedColumn: (col) =>
    set({ focusedColumn: col }),

  setSort: (field, direction) =>
    set({
      sort: field,
      sortDirection: direction,
      selectedRowId: null,
      selectedRowIndex: -1,
    }),

  clearSort: () =>
    set({
      sort: null,
      sortDirection: 'asc',
      selectedRowId: null,
      selectedRowIndex: -1,
    }),

  setSearch: (search) =>
    set({ search, selectedRowId: null, selectedRowIndex: -1 }),

  toggleQuickFilter: (filter) =>
    set((state) => {
      const exists = state.quickFilters.some(
        (qf) =>
          qf.field_key === filter.field_key &&
          qf.operator === filter.operator &&
          qf.value === filter.value,
      )
      return {
        quickFilters: exists
          ? state.quickFilters.filter(
              (qf) =>
                !(
                  qf.field_key === filter.field_key &&
                  qf.operator === filter.operator &&
                  qf.value === filter.value
                ),
            )
          : [...state.quickFilters, filter],
        selectedRowId: null,
        selectedRowIndex: -1,
      }
    }),

  setPendingNavigation: (nav) => set({ pendingNavigation: nav }),

  reset: () => set(DEFAULTS),
}))
