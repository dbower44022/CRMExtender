import { useQuery } from '@tanstack/react-query'
import { get } from './client.ts'

export interface SearchResultItem {
  id: string
  name: string
  subtitle?: string
  secondary?: string
}

export interface SearchGroup {
  entity_type: string
  label: string
  total: number
  results: SearchResultItem[]
}

export interface GroupedSearchResponse {
  groups: SearchGroup[]
  total: number
}

export function useGlobalSearch(
  query: string,
  options?: { entityType?: string; limit?: number },
) {
  const params = new URLSearchParams({ q: query })
  if (options?.entityType) params.set('entity_type', options.entityType)
  if (options?.limit) params.set('limit', String(options.limit))

  return useQuery({
    queryKey: ['search', query, options?.entityType ?? '', options?.limit ?? 5],
    queryFn: () => get<GroupedSearchResponse>(`/search?${params.toString()}`),
    enabled: query.length >= 2,
    staleTime: 10 * 1000,
  })
}
