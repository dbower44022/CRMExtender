import { create } from 'zustand'
import type { QuickFilter } from '../types/api.ts'

interface NavigationState {
  activeEntityType: string
  activeViewId: string | null
  selectedRowId: string | null
  selectedRowIndex: number
  sort: string | null
  sortDirection: 'asc' | 'desc'
  search: string
  quickFilters: QuickFilter[]

  setActiveEntityType: (entityType: string) => void
  setActiveViewId: (viewId: string | null) => void
  setSelectedRow: (id: string | null, index: number) => void
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
      quickFilters: [],
    }),

  setSelectedRow: (id, index) =>
    set({ selectedRowId: id, selectedRowIndex: index }),

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
