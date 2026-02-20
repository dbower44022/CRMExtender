import { useQuery } from '@tanstack/react-query'
import { get } from './client.ts'

interface SearchResult {
  entity_type: string
  id: string
  name: string
  subtitle?: string
}

interface SearchResponse {
  results: SearchResult[]
  total: number
}

export function useSearch(query: string) {
  return useQuery({
    queryKey: ['search', query],
    queryFn: () => get<SearchResponse>(`/search?q=${encodeURIComponent(query)}`),
    enabled: query.length >= 2,
    staleTime: 10 * 1000,
  })
}

export type { SearchResult, SearchResponse }
