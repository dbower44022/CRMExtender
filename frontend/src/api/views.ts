import { useQuery, useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { get, post, put, del } from './client.ts'
import type {
  View,
  ViewDataResponse,
  CreateViewRequest,
  UpdateViewRequest,
  UpdateColumnsRequest,
  UpdateFiltersRequest,
  CellEditRequest,
  CellEditResponse,
  QuickFilter,
} from '../types/api.ts'

export function useViews(entityType: string | null) {
  return useQuery({
    queryKey: ['views', entityType],
    queryFn: () => get<View[]>(`/views?entity_type=${entityType}`),
    enabled: !!entityType,
    staleTime: 30 * 1000,
  })
}

export function useViewConfig(viewId: string | null) {
  return useQuery({
    queryKey: ['view-config', viewId],
    queryFn: () => get<View>(`/views/${viewId}`),
    enabled: !!viewId,
    staleTime: 30 * 1000,
  })
}

interface InfiniteViewDataParams {
  viewId: string | null
  sort?: string | null
  sortDirection?: 'asc' | 'desc'
  search?: string
  quickFilters?: QuickFilter[]
}

export function useInfiniteViewData({
  viewId,
  sort,
  sortDirection,
  search = '',
  quickFilters = [],
}: InfiniteViewDataParams) {
  return useInfiniteQuery({
    queryKey: ['view-data', viewId, sort, sortDirection, search, quickFilters],
    queryFn: ({ pageParam = 1 }) => {
      const params = new URLSearchParams()
      params.set('page', String(pageParam))
      if (sort) params.set('sort', sort)
      if (sortDirection) params.set('sort_direction', sortDirection)
      if (search) params.set('search', search)
      if (quickFilters.length > 0) {
        params.set('filters', JSON.stringify(quickFilters))
      }
      return get<ViewDataResponse>(`/views/${viewId}/data?${params.toString()}`)
    },
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.has_more ? lastPage.page + 1 : undefined,
    enabled: !!viewId,
    staleTime: 15 * 1000,
  })
}

// --- Mutation hooks ---

export function useCreateView() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateViewRequest) => post<View>('/views', data),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ['views', variables.entity_type] })
    },
  })
}

export function useUpdateView(viewId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: UpdateViewRequest) => put<View>(`/views/${viewId}`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['view-config', viewId] })
      qc.invalidateQueries({ queryKey: ['views'] })
    },
  })
}

export function useUpdateViewColumns(viewId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: UpdateColumnsRequest) =>
      put<View>(`/views/${viewId}/columns`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['view-config', viewId] })
      qc.invalidateQueries({ queryKey: ['view-data'] })
    },
  })
}

export function useUpdateViewFilters(viewId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: UpdateFiltersRequest) =>
      put<View>(`/views/${viewId}/filters`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['view-config', viewId] })
      qc.invalidateQueries({ queryKey: ['view-data'] })
    },
  })
}

export function useDeleteView() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (viewId: string) => del<{ ok: boolean }>(`/views/${viewId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['views'] })
    },
  })
}

export function useDuplicateView() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ viewId, name }: { viewId: string; name?: string }) =>
      post<View>(`/views/${viewId}/duplicate`, name ? { name } : {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['views'] })
    },
  })
}

export function useCellEdit() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: CellEditRequest) =>
      post<CellEditResponse>('/cell-edit', data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['view-data'] })
    },
  })
}
