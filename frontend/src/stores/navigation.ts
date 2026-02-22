import { create } from 'zustand'
import type { QuickFilter } from '../types/api.ts'

interface NavigationState {
  activeEntityType: string
  activeViewId: string | null
  selectedRowId: string | null
  selectedRowIndex: number
  selectedRowIds: Set<string>
  loadedRowCount: number
  sort: string | null
  sortDirection: 'asc' | 'desc'
  search: string
  quickFilters: QuickFilter[]

  setActiveEntityType: (entityType: string) => void
  setActiveViewId: (viewId: string | null) => void
  setSelectedRow: (id: string | null, index: number) => void
  toggleRowSelection: (id: string) => void
  selectAllRows: (ids: string[]) => void
  deselectAllRows: () => void
  setLoadedRowCount: (count: number) => void
  setSort: (field: string, direction: 'asc' | 'desc') => void
  setSearch: (search: string) => void
  toggleQuickFilter: (filter: QuickFilter) => void
  reset: () => void
}

const DEFAULTS = {
  activeEntityType: 'contact',
  activeViewId: null as string | null,
  selectedRowId: null as string | null,
  selectedRowIndex: -1,
  selectedRowIds: new Set<string>(),
  loadedRowCount: 0,
  sort: null as string | null,
  sortDirection: 'asc' as const,
  search: '',
  quickFilters: [] as QuickFilter[],
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
      quickFilters: [],
    }),

  setSelectedRow: (id, index) =>
    set({ selectedRowId: id, selectedRowIndex: index }),

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

  setLoadedRowCount: (count) =>
    set({ loadedRowCount: count }),

  setSort: (field, direction) =>
    set({
      sort: field,
      sortDirection: direction,
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

  reset: () => set(DEFAULTS),
}))
