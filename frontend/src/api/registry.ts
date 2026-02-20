import { useQuery } from '@tanstack/react-query'
import { get } from './client.ts'
import type { EntityDef } from '../types/api.ts'

export function useEntityRegistry() {
  return useQuery({
    queryKey: ['entity-registry'],
    queryFn: () => get<Record<string, EntityDef>>('/entity-types'),
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  })
}
