import { create } from 'zustand'

interface NavigationState {
  activeEntityType: string
  activeViewId: string | null
  selectedRowId: string | null
  selectedRowIndex: number
  page: number
  sort: string | null
  sortDirection: 'asc' | 'desc'
  search: string

  setActiveEntityType: (entityType: string) => void
  setActiveViewId: (viewId: string | null) => void
  setSelectedRow: (id: string | null, index: number) => void
  setPage: (page: number) => void
  setSort: (field: string, direction: 'asc' | 'desc') => void
  setSearch: (search: string) => void
  reset: () => void
}

const DEFAULTS = {
  activeEntityType: 'contact',
  activeViewId: null as string | null,
  selectedRowId: null as string | null,
  selectedRowIndex: -1,
  page: 1,
  sort: null as string | null,
  sortDirection: 'asc' as const,
  search: '',
}

export const useNavigationStore = create<NavigationState>()((set) => ({
  ...DEFAULTS,

  setActiveEntityType: (entityType) =>
    set({
      activeEntityType: entityType,
      activeViewId: null,
      selectedRowId: null,
      selectedRowIndex: -1,
      page: 1,
      sort: null,
      sortDirection: 'asc',
      search: '',
    }),

  setActiveViewId: (viewId) =>
    set({
      activeViewId: viewId,
      selectedRowId: null,
      selectedRowIndex: -1,
      page: 1,
    }),

  setSelectedRow: (id, index) =>
    set({ selectedRowId: id, selectedRowIndex: index }),

  setPage: (page) => set({ page, selectedRowId: null, selectedRowIndex: -1 }),

  setSort: (field, direction) =>
    set({
      sort: field,
      sortDirection: direction,
      page: 1,
      selectedRowId: null,
      selectedRowIndex: -1,
    }),

  setSearch: (search) =>
    set({ search, page: 1, selectedRowId: null, selectedRowIndex: -1 }),

  reset: () => set(DEFAULTS),
}))
