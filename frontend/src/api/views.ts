import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { get } from './client.ts'
import type { View, ViewDataResponse } from '../types/api.ts'

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

interface ViewDataParams {
  viewId: string | null
  page?: number
  sort?: string | null
  sortDirection?: 'asc' | 'desc'
  search?: string
}

export function useViewData({
  viewId,
  page = 1,
  sort,
  sortDirection,
  search = '',
}: ViewDataParams) {
  const params = new URLSearchParams()
  params.set('page', String(page))
  if (sort) params.set('sort', sort)
  if (sortDirection) params.set('sort_direction', sortDirection)
  if (search) params.set('search', search)

  return useQuery({
    queryKey: ['view-data', viewId, page, sort, sortDirection, search],
    queryFn: () =>
      get<ViewDataResponse>(`/views/${viewId}/data?${params.toString()}`),
    enabled: !!viewId,
    staleTime: 15 * 1000,
    placeholderData: keepPreviousData,
  })
}
